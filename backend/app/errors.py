"""Stable public error codes; English detail is retained for API compatibility."""

ERROR_CODES = {
    "Approved template requires .xlsx": "APPROVED_XLSX_REQUIRED",
    "Approved workbook exceeds limits": "APPROVED_WORKBOOK_LIMIT",
    "Approved workbook contains no properties": "APPROVED_WORKBOOK_EMPTY",
    "Correct all workbook errors before importing": "APPROVED_WORKBOOK_ERRORS",
    "Workbook properties already exist in this project": "APPROVED_WORKBOOK_DUPLICATE",
    "Administrator access required": "ADMIN_REQUIRED",
    "Email already registered": "EMAIL_REGISTERED",
    "User not found": "USER_NOT_FOUND",
    "Cannot disable an administrator": "ADMIN_PROTECTED",
    "Too many login attempts. Try again in five minutes.": "TOO_MANY_LOGIN_ATTEMPTS_TRY_AGAIN_IN_FIVE_MINUTES",
    "Invalid email or password": "INVALID_EMAIL_OR_PASSWORD",
    "Please sign in": "PLEASE_SIGN_IN",
    "Image not found": "IMAGE_NOT_FOUND",
    "Mapping must be a JSON object": "MAPPING_MUST_BE_A_JSON_OBJECT",
    "Import not found": "IMPORT_NOT_FOUND",
    "This workbook preview has already been imported": "THIS_WORKBOOK_PREVIEW_HAS_ALREADY_BEEN_IMPORTED",
    "No valid rows to import": "NO_VALID_ROWS_TO_IMPORT",
    "Item does not belong to this project": "ITEM_DOES_NOT_BELONG_TO_THIS_PROJECT",
    "Mapping must be valid JSON": "MAPPING_MUST_BE_VALID_JSON",
    "Project not found": "PROJECT_NOT_FOUND",
    "Output not found": "OUTPUT_NOT_FOUND",
    "File exceeds upload limit": "FILE_EXCEEDS_UPLOAD_LIMIT",
    "Use the logo upload endpoint to change the logo": "USE_THE_LOGO_UPLOAD_ENDPOINT_TO_CHANGE_THE_LOGO",
    "Item not found": "ITEM_NOT_FOUND",
    "A project with this reference already exists": "A_PROJECT_WITH_THIS_REFERENCE_ALREADY_EXISTS",
    "Project reference already exists": "PROJECT_REFERENCE_ALREADY_EXISTS",
    "Unknown output type": "UNKNOWN_OUTPUT_TYPE",
    "Add at least one item before generating outputs": "ADD_AT_LEAST_ONE_ITEM_BEFORE_GENERATING_OUTPUTS",
    "Source data changed. Regenerate first.": "SOURCE_DATA_CHANGED_REGENERATE_FIRST",
    "Source data changed. Regenerate before approval.": "SOURCE_DATA_CHANGED_REGENERATE_BEFORE_APPROVAL",
    "File not found": "FILE_NOT_FOUND",
    "Approve this output before exporting it": "APPROVE_THIS_OUTPUT_BEFORE_EXPORTING_IT",
    "Templates are not initialized. Run the bootstrap command.": "TEMPLATES_ARE_NOT_INITIALIZED_RUN_THE_BOOTSTRAP_COMMAND",
    "Only .xlsx and .xls workbooks are supported": "ONLY_XLSX_AND_XLS_WORKBOOKS_ARE_SUPPORTED",
    "Mapping contains an unknown target field": "MAPPING_CONTAINS_AN_UNKNOWN_TARGET_FIELD",
    "Workbook contains no data rows": "WORKBOOK_CONTAINS_NO_DATA_ROWS",
    "Could not read workbook. Check its format and remove password protection.": "COULD_NOT_READ_WORKBOOK_CHECK_ITS_FORMAT_AND_REMOVE_PASSWORD_PROTECTION",
    "Import at most 5,000 rows at a time": "IMPORT_AT_MOST_5_000_ROWS_AT_A_TIME",
    "Invalid Excel workbook": "INVALID_EXCEL_WORKBOOK",
    "Workbook expands beyond the 50 MB limit": "WORKBOOK_EXPANDS_BEYOND_THE_50_MB_LIMIT",
    "Invalid file key": "INVALID_FILE_KEY",
    "Image exceeds upload limit": "IMAGE_EXCEEDS_UPLOAD_LIMIT",
    "Use a valid JPEG, PNG or WebP image, up to 25 megapixels": "USE_A_VALID_JPEG_PNG_OR_WEBP_IMAGE_UP_TO_25_MEGAPIXELS",
    "Origin not allowed": "ORIGIN_NOT_ALLOWED",
    "The operation failed. Please try again or contact the administrator.": "THE_OPERATION_FAILED_PLEASE_TRY_AGAIN_OR_CONTACT_THE_ADMINISTRATOR",
}


def violations(errors):
    return [
        {
            "field": ".".join(
                str(v) for v in e["loc"] if v not in ("body", "query", "path")
            ),
            "type": e["type"],
            "context": {
                k: v
                for k, v in e.get("ctx", {}).items()
                if isinstance(v, (str, int, float))
            },
        }
        for e in errors
    ]


ERROR_CODES.update(
    {
        "Complete the auction review before generation": "COMPLETE_AUCTION_REVIEW",
        "Edit auction data and regenerate the booklet": "EDIT_AUCTION_DATA",
        "Multiple columns map to the same field": "DUPLICATE_COLUMN_MAPPING",
        "Logo must belong to this project": "PROJECT_LOGO_REQUIRED",
        "Provide every project item exactly once": "INVALID_PROPERTY_ORDER",
    }
)
