# HUMANA_SILVER.MEDCLAIM Table

The `MEDCLAIM` table is a crucial component within the `HUMANA_SILVER` schema, containing detailed line-item information for medical claims. This table captures the granular elements necessary for processing, auditing, and analyzing individual healthcare services provided under the medicare platform. Each row represents a specific service line on a claim.

## Fields:

| Field Name           | Data Type | Description                                                               |
| :------------------- | :-------- | :------------------------------------------------------------------------ |
| `CLAIM_LINE_EDEN_UID` | STRING    | Unique system-generated identifier for each claim line item.              |
| `CLAIM_SUMMARY_EDEN_UID` | STRING    | Unique system-generated identifier linking to the overall claim summary (referencing `MEDCLAIM_SUMMARY`). |
| `LOAD_MONTH`         | DATE      | The calendar month when this specific claim line data was loaded into the system. |
| `CLAIM_LINE_UID`     | STRING    | The original unique identifier for the claim line as provided by the source system. |
| `PAID_AMOUNT`        | DECIMAL   | The monetary amount that was paid for this particular claim line item.    |
| `FIRST_DOS`          | DATE      | The earliest Date Of Service for the healthcare procedure or service on this claim line. |
| `LAST_DOS`           | DATE      | The latest Date Of Service for the healthcare procedure or service on this claim line. |
| `CPT_CODE`           | STRING    | Current Procedural Terminology code, representing a medical procedure or service. |
| `HCPCS_CODE`         | STRING    | Healthcare Common Procedure Coding System code, used for reporting medical supplies, services, and procedures. |
| `DIAGNOSIS_CODE_PRIMARY` | STRING    | The primary diagnosis code (e.g., ICD-10) associated with the medical service rendered. |
| `PROCEDURE_CODE`     | STRING    | Code identifying the specific medical procedure performed, often a CPT or HCPCS code. |
| `PROVIDER_ID`        | STRING    | Identifier for the rendering healthcare provider who performed the service. |
| `MEMBER_ID`          | STRING    | Identifier for the member who received the healthcare service.            |
| `SERVICE_TYPE`       | STRING    | Categorization of the healthcare service (e.g., Office Visit, Surgery, Lab). |