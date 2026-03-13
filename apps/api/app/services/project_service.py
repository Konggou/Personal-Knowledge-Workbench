from app.repositories.project_repository import ProjectRepository


class ProjectService:
    def __init__(self) -> None:
        self.repository = ProjectRepository()

    def list_projects(self, *, include_archived: bool = False, query: str | None = None) -> list[dict]:
        return [record.to_summary() for record in self.repository.list_projects(include_archived=include_archived, query=query)]

    def get_project(self, project_id: str) -> dict | None:
        record = self.repository.get_project(project_id)
        return None if record is None else record.to_summary()

    def create_project(
        self,
        *,
        name: str,
        description: str,
        default_external_policy: str,
    ) -> dict:
        record = self.repository.create_project(
            name=name,
            description=description,
            default_external_policy=default_external_policy,
        )
        return record.to_summary()
