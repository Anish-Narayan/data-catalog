# Glossary

This glossary defines common terms used throughout the Payment Integrity Data Catalog.

<a id="claim"></a>
## Claim
**Definition:** A formal request for payment submitted by a healthcare provider to an insurer for services rendered to a patient.
**Context:** Claims contain detailed information about the services, dates, costs, and patient.

<a id="member"></a>
## Member
**Definition:** An individual who is covered by a health insurance plan or is a beneficiary of healthcare services.
**Context:** Members are uniquely identified and linked to their health records and claims.

<a id="provider"></a>
## Provider
**Definition:** A healthcare professional (e.g., doctor, nurse, therapist) or an organization (e.g., hospital, clinic, lab) that provides healthcare services.
**Context:** Providers submit claims for the services they render.

<a id="adjudication"></a>
## Adjudication
**Definition:** The process by which an insurance company reviews a claim and determines whether to pay it, deny it, or pay it at a reduced rate, based on policy terms and clinical guidelines.
**Context:** This process often results in a 'Paid Amount' and a 'Claim Status'.

<a id="cpt_code"></a>
## CPT Code (Current Procedural Terminology)
**Definition:** A set of medical codes used by physicians and other healthcare providers to report medical, surgical, and diagnostic procedures and services to entities such as physicians, health insurance companies and accreditation organizations.
**Context:** Used in `CLAIM_LINE` to describe the service provided.

<a id="allowed_amount"></a>
## Allowed Amount
**Definition:** The maximum amount a plan will pay for a covered health care service. This may also be called “eligible expense,” “payment allowance,” or “negotiated rate.”
**Context:** The negotiated rate between the payer and provider for a specific service.