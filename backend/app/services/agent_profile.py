"""An account owns the selling-agent identity used by all its publications."""

from sqlalchemy import select
from ..models import Project, ProjectImage, SellingAgent

REQUIRED = ("name", "description", "phone")


def complete(user):
    data = user.agent_profile or {}
    return all(str(data.get(k, "")).strip() for k in (*REQUIRED, "logo_key"))


def initial_profile(db, user):
    if user.agent_profile:
        return dict(user.agent_profile)
    # Existing customers can confirm their most recent identity once, without retyping.
    row = db.scalar(
        select(SellingAgent)
        .join(Project, Project.id == SellingAgent.project_id)
        .where(Project.owner_id == user.id)
        .order_by(Project.created_at.desc())
    )
    if not row:
        return {}
    data = dict(row.data)
    image = db.scalar(
        select(ProjectImage).where(
            ProjectImage.id == data.pop("logo_image_id", ""),
            ProjectImage.project_id == row.project_id,
            ProjectImage.item_id.is_(None),
        )
    )
    if image:
        data["logo_key"] = image.key
    return data


def apply_profile(db, user, project):
    if not complete(user):
        return False
    data = {k: v for k, v in user.agent_profile.items() if k != "logo_key"}
    key = user.agent_profile["logo_key"]
    image = db.scalar(
        select(ProjectImage).where(
            ProjectImage.project_id == project.id,
            ProjectImage.category == "agent_logo",
            ProjectImage.key == key,
            ProjectImage.item_id.is_(None),
        )
    )
    if not image:
        image = ProjectImage(
            project_id=project.id,
            category="agent_logo",
            key=key,
            caption=data["name"],
            orientation="landscape",
            sequence_number=0,
        )
        db.add(image)
        db.flush()
    data["logo_image_id"] = image.id
    agent = db.scalar(select(SellingAgent).where(SellingAgent.project_id == project.id))
    if agent and agent.data == data:
        return False
    if not agent:
        agent = SellingAgent(project_id=project.id)
        db.add(agent)
    agent.data = data
    return True
