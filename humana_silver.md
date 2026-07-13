# HUMANA_SILVER Schema

The `HUMANA_SILVER` schema is an intermediate data layer where raw claims data undergoes initial processing, cleaning, and concept application. In this schema, detailed claim information is present, and various business logic and payment integrity concepts are applied to prepare the data for the `HUMANA_GOLD` (analytics) layer. This layer bridges the gap between raw source data and refined analytical data, ensuring data quality and consistency.

## Key Tables in HUMANA_SILVER:

*   **MEDCLAIM**: Contains detailed line-item claim data, including service dates, CPT codes, and paid amounts. [Link to Medclaim Details](medclaim.md)
*   **MEDCLAIM_SUMMARY**: Provides aggregated claim summary information, offering a high-level view of claim financials. [Link to Medclaim Summary Details](medclaimsummary.md)
*   **PROVIDER**: Stores comprehensive information about healthcare providers, including their specialties, NPIs, and network affiliations.
*   **MEMBER**: Contains demographic and enrollment details for members covered under the medicare platform, essential for linking claims to individuals.
*   **DRUG_UTILIZATION**: Tracks prescription drug usage and related details, critical for pharmacy benefits management and identifying potential drug fraud or abuse.
*   **DIAGNOSIS_CODES**: A reference table for medical diagnosis codes (e.g., ICD-10), used to categorize and understand the health conditions associated with claims.