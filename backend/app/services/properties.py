from sqlalchemy import delete, select

from ..models import ProjectItem, RentalContract
from .ingestion import normalize


def save_item(db, project_id, data, item=None):
    values = normalize(data)
    rentals = values["property_data"].pop("rental_contracts", [])
    if item is None:
        item = ProjectItem(project_id=project_id)
        if not values["sequence_number"]:
            existing = db.scalars(
                select(ProjectItem.sequence_number).where(
                    ProjectItem.project_id == project_id
                )
            ).all()
            values["sequence_number"] = max(existing, default=0) + 1
    elif not values["sequence_number"]:
        values["sequence_number"] = item.sequence_number
    for key, value in values.items():
        setattr(item, key, value)
    db.add(item)
    db.flush()
    db.execute(delete(RentalContract).where(RentalContract.item_id == item.id))
    for i, row in enumerate(rentals):
        db.add(RentalContract(item_id=item.id, sequence_number=i, data=row))
    db.flush()
    return item


def item_view(db, item):
    result = {c.name: getattr(item, c.name) for c in item.__table__.columns}
    result["property_data"] = {
        **item.property_data,
        "rental_contracts": [
            r.data
            for r in db.scalars(
                select(RentalContract)
                .where(RentalContract.item_id == item.id)
                .order_by(RentalContract.sequence_number)
            )
        ],
    }
    return result
