# HUMANA_SILVER.MEDCLAIM_SUMMARY Table

The `MEDCLAIM_SUMMARY` table, also part of the `HUMANA_SILVER` schema, provides an aggregated view of medical claims. It summarizes key financial and administrative details for an entire claim, allowing for high-level analysis and reporting without needing to delve into every claim line. This table is essential for understanding the overall cost and status of each submitted claim.

## Fields:

| Field Name           | Data Type | Description                                                               |
| :------------------- | :-------- | :------------------------------------------------------------------------ |
| `CLAIM_NUMBER`       | STRING    | The unique identifier assigned to the entire medical claim by the payer.  |
| `TOTAL_CHARGED_AMOUNT` | DECIMAL   | The sum of all charged amounts across all line items for this claim.      |
| `TOTAL_PAID_AMOUNT`  | DECIMAL   | The total monetary amount that was paid for the entire claim.             |
| `CLAIM_STATUS`       | STRING    | Current status of the claim (e.g., 'Paid', 'Denied', 'Pended', 'Adjusted'). |
| `SUBMISSION_DATE`    | DATE      | The date the claim was originally submitted by the provider or member.    |
| `ADJUDICATION_DATE`  | DATE      | The date when the claim underwent its final processing and a payment decision was made. |
| `PLAN_TYPE`          | STRING    | The type of health plan or program under which the claim was filed (e.g., 'Medicare Part A', 'Medicare Part B'). |
| `MEMBER_ID`          | STRING    | Identifier for the member associated with the overall claim.              |
| `PROVIDER_ID`        | STRING    | Identifier for the primary billing provider or facility on the claim.    |