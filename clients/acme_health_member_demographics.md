# MEMBER_DEMOGRAPHICS (Acme Health)

## Purpose
Contains demographic and enrollment information for each member, crucial for contextualizing claims data and member-specific analytics.

## Fields

| Field       | Meaning                                   | Data Type   | Example          |
|-------------|-------------------------------------------|-------------|------------------|
| MEMBER_ID   | Unique member identifier                  | VARCHAR(50) | 'MEM-98765'      |
| FIRST_NAME  | Member's first name                       | VARCHAR(100)| 'Alice'          |
| LAST_NAME   | Member's last name                        | VARCHAR(100)| 'Smith'          |
| DATE_OF_BIRTH | Member's date of birth                  | DATE        | '1985-06-15'     |
| GENDER      | Member's gender (M/F/O)                   | VARCHAR(1)  | 'F'              |
| ZIP_CODE    | Member's residential ZIP code             | VARCHAR(10) | '90210'          |
| PLAN_TYPE   | Type of insurance plan (e.g., HMO, PPO)   | VARCHAR(50) | 'PPO'            |
| ENROLLMENT_START_DATE | Date member enrolled in plan  | DATE        | '2020-01-01'     |

## Related Tables

-   [CLAIM_HEADER](clients/claim_header.md) (One-to-many: One MEMBER_DEMOGRAPHICS to many CLAIM_HEADERs via MEMBER_ID)

## Sample Data

```sql
SELECT
    MEMBER_ID,
    FIRST_NAME,
    LAST_NAME,
    DATE_OF_BIRTH,
    PLAN_TYPE
FROM
    ACMEHEALTH.MEMBER_DEMOGRAPHICS
WHERE
    ZIP_CODE = '90210'
LIMIT 5;
code
Code
**7. `clients/bright_care.md`**```markdown
# Bright Care

## Overview

**Pod:** Patient Engagement, Quality Reporting
**Program:** Patient Outcome Tracking, Provider Performance Analysis

Bright Care focuses on integrating patient care across various facilities. Their data assets support tracking patient journeys, managing provider networks, and assessing quality metrics.

## Key Data Domains

*   **Patient Visit Data:** Records of patient encounters at facilities.
*   **Provider Data:** Information about healthcare professionals and their affiliations.

## Tables

-   [PATIENT_VISITS](clients/bright_care_patient_visits.md)
-   [PROVIDERS](clients/bright_care_providers.md)