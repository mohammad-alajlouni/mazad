import json
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi import HTTPException
from pydantic import ValidationError

from ..auction_schemas import Boundaries, PropertyData
from ..errors import violations
from ..schemas import ItemInput

DEFAULT_MAPPING = json.loads(
    (Path(__file__).parent.parent / "templates/excel_mapping.json").read_text()
)

PROPERTY_TARGETS = {
    f"property.{k}"
    for k in PropertyData.model_fields
    if k not in ("boundaries", "rental_contracts")
}
PROPERTY_TARGETS |= {f"property.boundaries.{k}" for k in Boundaries.model_fields}
DEFAULT_MAPPING.update(
    {
        "نوع العقار": "property.property_type",
        "المدينة": "property.city",
        "الحي": "property.district",
        "المساحة": "property.area",
        "رقم الصك": "property.deed_number",
        "رقم القطعة": "property.plot_number",
        "رقم المخطط": "property.plan_number",
        "رقم طلب التنفيذ": "property.execution_request_number",
        "مبلغ المشاركة": "property.participation_amount",
        "الاستخدام": "property.usage",
        "وصف العقار": "description",
        "المميزات": "property.features",
        "معلومات إضافية": "property.additional_information",
        **{
            k: f"property.{k}"
            for k in PropertyData.model_fields
            if k not in ("boundaries", "rental_contracts")
        },
    }
)


def normalize(data):
    clean = {k: v for k, v in data.items() if v is not None and v != ""}
    for key in ("quantity", "financial_value"):
        if isinstance(clean.get(key), str):
            clean[key] = clean[key].replace(",", "").strip()
    prop = dict(clean.get("property_data") or {})
    for key in ("area", "participation_amount"):
        if isinstance(prop.get(key), str):
            prop[key] = (
                prop[key]
                .translate(str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,"))
                .replace(",", "")
            )
    clean["property_data"] = prop
    return ItemInput.model_validate(clean).model_dump(mode="json")


def parse_excel(data, filename, mapping=None):
    suffix = Path(filename).suffix.lower()
    if suffix not in (".xlsx", ".xls"):
        raise HTTPException(400, "Only .xlsx and .xls workbooks are supported")
    if suffix == ".xlsx":
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                if sum(x.file_size for x in archive.infolist()) > 50 * 1024 * 1024:
                    raise HTTPException(400, "Workbook expands beyond the 50 MB limit")
        except zipfile.BadZipFile:
            raise HTTPException(400, "Invalid Excel workbook")
    aliases = {
        str(k).strip().lower(): v
        for k, v in {**DEFAULT_MAPPING, **(mapping or {})}.items()
    }
    if any(
        v not in ItemInput.model_fields
        and v not in ("image_reference", "__ignore__")
        and v not in PROPERTY_TARGETS
        for v in aliases.values()
    ):
        raise HTTPException(400, "Mapping contains an unknown target field")
    try:
        sheets = pd.read_excel(
            BytesIO(data),
            sheet_name=None,
            dtype=object,
            header=None,
            engine="openpyxl" if suffix == ".xlsx" else "xlrd",
        )
    except Exception:
        raise HTTPException(
            400,
            "Could not read workbook. Check its format and remove password protection.",
        )
    result = []
    seen = set()
    for sheet, frame in sheets.items():
        if frame.empty:
            continue

        def target(header):
            key = str(header).strip().lower()
            return aliases.get(
                key,
                key
                if key in ItemInput.model_fields or key in PROPERTY_TARGETS
                else None,
            )

        candidates = [
            (sum(bool(target(v)) for v in frame.iloc[i].dropna()), i)
            for i in range(min(30, len(frame)))
        ]
        header_index = max(candidates, key=lambda x: (x[0], -x[1]))[1]
        headers = [
            str(v).strip() if pd.notna(v) else f"Column {i + 1}"
            for i, v in enumerate(frame.iloc[header_index])
        ]
        targets = [
            target(h) for h in headers if target(h) and target(h) != "__ignore__"
        ]
        if len(targets) != len(set(targets)):
            raise HTTPException(400, "Multiple columns map to the same field")
        frame = frame.iloc[header_index + 1 :].copy()
        frame.columns = headers
        if len(frame) > 5000 or len(result) + len(frame) > 5000:
            raise HTTPException(400, "Import at most 5,000 rows at a time")
        for i, row in frame.iterrows():
            source = {str(k).strip(): v for k, v in row.items() if pd.notna(v)}
            if not source:
                continue
            mapped = {}
            attributes = {}
            prop = {}
            for key, value in source.items():
                target = aliases.get(
                    key.lower(),
                    key.lower()
                    if key.lower() in ItemInput.model_fields
                    or key.lower() in PROPERTY_TARGETS
                    else None,
                )
                if target == "__ignore__":
                    continue
                if target and target.startswith("property."):
                    field = target.removeprefix("property.")
                    value = str(value).strip()
                    if field.startswith("boundaries."):
                        prop.setdefault("boundaries", {})[field.split(".", 1)[1]] = (
                            value
                        )
                    elif field == "features":
                        prop[field] = [
                            v.strip() for v in value.split("\n") if v.strip()
                        ]
                    elif field.endswith("_date"):
                        prop[field] = value[:10]
                    else:
                        prop[field] = value
                elif target == "image_reference":
                    attributes["image_reference"] = str(value)
                elif target:
                    mapped[target] = (
                        value
                        if target in ("quantity", "financial_value")
                        else str(value).strip()
                    )
                else:
                    attributes[key] = str(value)
            if "attributes" in mapped:
                try:
                    attributes.update(json.loads(mapped.pop("attributes")))
                except (ValueError, TypeError):
                    pass
            mapped["property_data"] = prop
            if not mapped.get("title") and prop.get("property_type"):
                mapped["title"] = " · ".join(
                    str(prop.get(k, ""))
                    for k in ("property_type", "city", "district")
                    if prop.get(k)
                )
            mapped["attributes"] = attributes
            try:
                normalized = normalize(mapped)
                errors = []
                issues = []
            except ValidationError as error:
                issues = [
                    {**v, "original_value": str(e.get("input", ""))}
                    for v, e in zip(violations(error.errors()), error.errors())
                ]
                normalized = {
                    k: str(v) if not isinstance(v, dict) else v
                    for k, v in mapped.items()
                }
                errors = [
                    f"{'.'.join(map(str, e['loc']))}: {e['msg']}"
                    for e in error.errors()
                ]
            fingerprint = json.dumps(source, sort_keys=True, default=str)
            if fingerprint in seen:
                errors.append("Duplicate row")
                issues.append({"field": "row", "type": "duplicate", "context": {}})
            seen.add(fingerprint)
            result.append(
                {
                    "sheet": sheet,
                    "row_number": int(i) + 1,
                    "source": {k: str(v) for k, v in source.items()},
                    "columns": [
                        {
                            "header": h,
                            "target": aliases.get(
                                h.lower(),
                                h.lower()
                                if h.lower() in ItemInput.model_fields
                                or h.lower() in PROPERTY_TARGETS
                                else "",
                            ),
                        }
                        for h in headers
                    ],
                    "data": normalized,
                    "errors": errors,
                    "issues": issues,
                }
            )
    if not result:
        raise HTTPException(400, "Workbook contains no data rows")
    return result
