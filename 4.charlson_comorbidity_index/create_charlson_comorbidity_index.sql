CREATE OR REPLACE TABLE `{{OUTPUT_NAMESPACE}}.charlson_concepts` (
  diag_category_id INT64,
  concept_id INT64
);

CREATE OR REPLACE TABLE `{{OUTPUT_NAMESPACE}}.charlson_scoring` (
  diag_category_id INT64,
  diag_category_name STRING,
  weight INT64
);

-- Insert data into `charlson_scoring` for Myocardial infarction
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (diag_category_id, diag_category_name, weight)
VALUES
  (1, 'Myocardial infarction', 1);

-- Insert data into `charlson_concepts` for Myocardial infarction
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (diag_category_id, concept_id)
SELECT 1, descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (4329847);

-- Repeat similar blocks for other conditions, e.g., Congestive heart failure, etc.
-- Congestive heart failure
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (diag_category_id, diag_category_name, weight)
VALUES
  (2, 'Congestive heart failure', 1);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (diag_category_id, concept_id)
SELECT 2, descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (316139);

--Peripheral vascular disease

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (diag_category_id, diag_category_name, weight)
VALUES
  (3,
	'Peripheral vascular disease',
	1);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (diag_category_id, concept_id)
SELECT 3, descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (321052);

--Cerebrovascular disease

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (diag_category_id, diag_category_name, weight)
VALUES
  (4, 'Cerebrovascular disease', 1);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (diag_category_id, concept_id)
SELECT 4, descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (381591, 434056);

--Dementia
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (
	diag_category_id,
	diag_category_name,
	weight
	)
VALUES (
	5,
	'Dementia',
	1
	);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (
	diag_category_id,
	concept_id
	)
SELECT 5,
	descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (4182210);

--Chronic pulmonary disease
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (
	diag_category_id,
	diag_category_name,
	weight
	)
VALUES (
	6,
	'Chronic pulmonary disease',
	1
	);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (
	diag_category_id,
	concept_id
	)
SELECT 6,
	descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (4063381);

--Rheumatologic disease
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (
	diag_category_id,
	diag_category_name,
	weight
	)
VALUES (
	7,
	'Rheumatologic disease',
	1
	);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (
	diag_category_id,
	concept_id
	)
SELECT 7,
	descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (257628, 134442, 80800, 80809, 256197, 255348);

--Peptic ulcer disease
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (
	diag_category_id,
	diag_category_name,
	weight
	)
VALUES (
	8,
	'Peptic ulcer disease',
	1
	);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (
	diag_category_id,
	concept_id
	)
SELECT 8,
	descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (4247120);

--Mild liver disease
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (
	diag_category_id,
	diag_category_name,
	weight
	)
VALUES (
	9,
	'Mild liver disease',
	1
	);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (
	diag_category_id,
	concept_id
	)
SELECT 9,
	descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (4064161, 4212540);

--Diabetes (mild to moderate)
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (
	diag_category_id,
	diag_category_name,
	weight
	)
VALUES (
	10,
	'Diabetes (mild to moderate)',
	1
	);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (
	diag_category_id,
	concept_id
	)
SELECT 10,
	descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (201820);

--Diabetes with chronic complications
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (
	diag_category_id,
	diag_category_name,
	weight
	)
VALUES (
	11,
	'Diabetes with chronic complications',
	2
	);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (
	diag_category_id,
	concept_id
	)
SELECT 11,
	descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (443767, 442793);

--Hemoplegia or paralegia
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (
	diag_category_id,
	diag_category_name,
	weight
	)
VALUES (
	12,
	'Hemoplegia or paralegia',
	2
	);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (
	diag_category_id,
	concept_id
	)
SELECT 12,
	descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (192606, 374022);

--Renal disease
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (
	diag_category_id,
	diag_category_name,
	weight
	)
VALUES (
	13,
	'Renal disease',
	2
	);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (
	diag_category_id,
	concept_id
	)
SELECT 13,
	descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (4030518);

--Any malignancy
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (
	diag_category_id,
	diag_category_name,
	weight
	)
VALUES (
	14,
	'Any malignancy',
	2
	);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (
	diag_category_id,
	concept_id
	)
SELECT 14,
	descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (443392);

--Moderate to severe liver disease
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (
	diag_category_id,
	diag_category_name,
	weight
	)
VALUES (
	15,
	'Moderate to severe liver disease',
	3
	);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (
	diag_category_id,
	concept_id
	)
SELECT 15,
	descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (4245975, 4029488, 192680, 24966);

--Metastatic solid tumor
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (
	diag_category_id,
	diag_category_name,
	weight
	)
VALUES (
	16,
	'Metastatic solid tumor',
	6
	);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (
	diag_category_id,
	concept_id
	)
SELECT 16,
	descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (432851);

--AIDS
INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_scoring` (
	diag_category_id,
	diag_category_name,
	weight
	)
VALUES (
	17,
	'AIDS',
	6
	);

INSERT INTO `{{OUTPUT_NAMESPACE}}.charlson_concepts` (
	diag_category_id,
	concept_id
	)
SELECT 17,
	descendant_concept_id
FROM `{{UNIONED_EHR_NAMESPACE}}.concept_ancestor`
WHERE ancestor_concept_id IN (439727);

