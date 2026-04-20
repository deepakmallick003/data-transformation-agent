from __future__ import annotations
from textwrap import dedent

from app.core.models import UserFacingStatus, WorkflowType
from app.transformation.capabilities import (
    artifact_targets_for_capabilities,
    capabilities_for_workflow,
    capability_ids_for_skills,
    default_skills_for_capabilities,
    list_capability_surfaces,
    list_runtime_abilities,
    normalize_skill_names,
    user_status_label_for_capability,
)
from app.transformation.models import (
    CapabilityId,
    CapabilitySurface,
    ExposureSurface,
    RuntimeAbilitySurface,
    StructuredTransformationRequest,
    TransformationExecutionPlan,
)


class TransformationCapabilityService:
    def list_capabilities(self) -> list[CapabilitySurface]:
        return list_capability_surfaces()

    def list_runtime_abilities(self) -> list[RuntimeAbilitySurface]:
        return list_runtime_abilities()

    def default_capabilities_for_workflow(self, workflow: WorkflowType) -> list[CapabilityId]:
        return capabilities_for_workflow(workflow)

    def default_skills_for_workflow(self, workflow: WorkflowType) -> list[str]:
        return default_skills_for_capabilities(self.default_capabilities_for_workflow(workflow))

    def build_user_facing_statuses(
        self,
        capabilities: list[CapabilityId],
        *,
        active: CapabilityId | None = None,
        blocked_reason: str | None = None,
    ) -> list[UserFacingStatus]:
        statuses: list[UserFacingStatus] = []
        seen: set[str] = set()
        for capability in capabilities:
            if capability in seen:
                continue
            seen.add(capability)
            state = "pending"
            detail = None
            if blocked_reason and capability == active:
                state = "blocked"
                detail = blocked_reason
            elif capability == active:
                state = "working"
            statuses.append(
                UserFacingStatus(
                    id=capability,
                    label=user_status_label_for_capability(capability),
                    state=state,
                    detail=detail,
                )
            )
        if blocked_reason:
            statuses.append(
                UserFacingStatus(
                    id="clarification",
                    label="Waiting for clarification",
                    state="blocked",
                    detail=blocked_reason,
                )
            )
        return statuses

    def inspect_request_evidence(self, objective: str, uploaded_files: list[str]) -> dict[str, object]:
        uploads_lower = [item.lower() for item in uploaded_files]
        objective_lower = objective.lower()
        upload_categories = {
            "csv_like": self._matching_uploads(uploads_lower, (".csv", ".tsv", ".xlsx", ".xls", ".parquet")),
            "json_like": self._matching_uploads(uploads_lower, (".json",)),
            "schema_like": [
                item
                for item in uploads_lower
                if item.endswith((".sql", ".ddl", ".dbml", ".yaml", ".yml", ".json"))
                and any(token in item for token in ("schema", "ddl", "target", "contract", "model"))
            ],
            "rules_like": [
                item
                for item in uploads_lower
                if any(token in item for token in ("rule", "mapping", "expected", "sample", "output", "spec"))
            ],
        }

        scenarios: list[dict[str, object]] = []
        scenario_defs = [
            (
                "csv_transformation",
                "CSV or tabular transformation",
                ("csv", "spreadsheet", "xlsx", "tsv", "customer records"),
                upload_categories["csv_like"],
                "Upload a representative CSV or spreadsheet sample.",
            ),
            (
                "postgres_target",
                "Postgres schema or table load",
                ("postgres", "postgresql", "ddl", "schema", "table"),
                upload_categories["schema_like"],
                "Upload target schema, DDL, or table contract details.",
            ),
            (
                "json_api_mapping",
                "JSON API response mapping",
                ("json api", "api response", "payload", "json mapping", "internal model"),
                upload_categories["json_like"],
                "Upload a representative JSON payload or API response sample.",
            ),
            (
                "python_pipeline",
                "Python cleaning or dedup pipeline",
                ("python", "pipeline", "dedup", "dedupe", "cleaning"),
                list(upload_categories["csv_like"]) + list(upload_categories["rules_like"]),
                "Upload business rules, expected outputs, or pipeline requirements.",
            ),
        ]

        for scenario_id, label, keywords, supporting_uploads, missing_step in scenario_defs:
            if not any(keyword in objective_lower for keyword in keywords):
                continue
            matched_uploads = sorted(set(str(item) for item in supporting_uploads))
            if matched_uploads:
                support = "supported"
                detail = f"Relevant uploads detected: {', '.join(matched_uploads)}."
            else:
                support = "missing"
                detail = missing_step
            scenarios.append(
                {
                    "id": scenario_id,
                    "label": label,
                    "support": support,
                    "detail": detail,
                }
            )

        source_uploads = sorted(set(upload_categories["csv_like"] + upload_categories["json_like"]))
        target_uploads = sorted(set(upload_categories["schema_like"]))
        missing_inputs = [item["detail"] for item in scenarios if item["support"] == "missing"]
        return {
            "scenarios": scenarios,
            "source_uploads": source_uploads,
            "target_uploads": target_uploads,
            "rules_uploads": sorted(set(upload_categories["rules_like"])),
            "missing_inputs": missing_inputs,
        }

    def plan_chat_turn(
        self,
        *,
        message: str,
        workflow: WorkflowType,
        skills: list[str] | None = None,
    ) -> TransformationExecutionPlan:
        normalized_skills = normalize_skill_names(skills)
        capabilities = capability_ids_for_skills(normalized_skills) or self.default_capabilities_for_workflow(
            workflow
        )
        resolved_skills = normalized_skills or default_skills_for_capabilities(capabilities)
        return TransformationExecutionPlan(
            objective=message,
            workflow=workflow,
            capabilities=capabilities,
            skills=resolved_skills,
            artifact_targets=artifact_targets_for_capabilities(capabilities),
            surface="chat",
            mode="chat",
        )

    def plan_structured_request(
        self,
        request: StructuredTransformationRequest,
        *,
        capability_override: CapabilityId | None = None,
        surface: ExposureSurface = "api",
    ) -> TransformationExecutionPlan:
        capabilities: list[CapabilityId] = list(request.capabilities)
        if capability_override is not None:
            capabilities = [capability_override]
        if not capabilities:
            capabilities = self.default_capabilities_for_workflow(request.workflow)

        normalized_skills = normalize_skill_names(request.skills)
        if normalized_skills:
            skill_capabilities = capability_ids_for_skills(normalized_skills)
            if capability_override is None and skill_capabilities:
                capabilities = skill_capabilities

        resolved_skills = normalized_skills or default_skills_for_capabilities(capabilities)
        objective = self._structured_objective(request, capabilities)
        return TransformationExecutionPlan(
            objective=objective,
            workflow=request.workflow,
            capabilities=capabilities,
            skills=resolved_skills,
            artifact_targets=artifact_targets_for_capabilities(capabilities),
            surface=surface,
            mode="structured",
            context=request.context,
            metadata={"requested_capabilities": request.capabilities},
        )

    def _structured_objective(
        self,
        request: StructuredTransformationRequest,
        capabilities: list[CapabilityId],
    ) -> str:
        context = request.context
        capability_list = ", ".join(capabilities)
        constraints = "\n".join(f"- {item}" for item in context.constraints) or "- none supplied"
        desired_outputs = (
            "\n".join(f"- {item}" for item in context.desired_outputs) or "- use the most appropriate deliverable"
        )
        uploads = "\n".join(f"- {item}" for item in context.uploads) or "- none referenced"
        metadata_lines = (
            "\n".join(f"- {key}: {value}" for key, value in context.metadata.items()) or "- none supplied"
        )
        return dedent(
            f"""
            Objective:
            {request.objective}

            Requested reusable capabilities:
            - {capability_list}

            Source context:
            {context.source_summary or "No explicit source summary supplied."}

            Target contract context:
            {context.target_summary or "No explicit target contract summary supplied."}

            Constraints:
            {constraints}

            Desired outputs:
            {desired_outputs}

            Referenced uploads:
            {uploads}

            Session notes:
            {context.notes or "No additional notes supplied."}

            Additional metadata:
            {metadata_lines}
            """
        ).strip()

    def build_turn_brief(self, objective: str, uploaded_files: list[str]) -> str:
        evidence = self.inspect_request_evidence(objective, uploaded_files)
        scenarios = evidence["scenarios"]
        source_uploads = evidence["source_uploads"]
        target_uploads = evidence["target_uploads"]
        missing_inputs = evidence["missing_inputs"]
        scenario_lines = (
            "\n".join(
                f"- {item['label']}: {item['support']} ({item['detail']})"
                for item in scenarios
            )
            or "- no distinct scenarios detected heuristically"
        )
        source_lines = (
            "\n".join(f"- {item}" for item in source_uploads)
            or "- no obvious source uploads detected"
        )
        target_lines = (
            "\n".join(f"- {item}" for item in target_uploads)
            or "- no obvious target/schema uploads detected"
        )
        missing_lines = (
            "\n".join(f"- {item}" for item in missing_inputs)
            or "- no required missing inputs detected heuristically"
        )
        return dedent(
            f"""
            Requested scenario coverage check:
            {scenario_lines}

            Source evidence uploads:
            {source_lines}

            Target or contract evidence uploads:
            {target_lines}

            Missing inputs to call out if still required:
            {missing_lines}
            """
        ).strip()

    def _matching_uploads(self, uploads: list[str], suffixes: tuple[str, ...]) -> list[str]:
        return [item for item in uploads if item.endswith(suffixes)]
