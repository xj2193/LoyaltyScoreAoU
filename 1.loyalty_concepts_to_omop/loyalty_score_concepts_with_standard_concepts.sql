SELECT lsc.*,
coalesce(cr.concept_id_2, c1.concept_id) AS STANDARD_CONCEPT,
c2.concept_id AS NON_STANDARD_CONCEPT,
coalesce(c.domain_id, c1.domain_id, c2.domain_id, 'None') as DOMAIN_ID
FROM `{{output_namespace}}.loyalty_score_concepts` lsc
LEFT JOIN `{{unioned_ehr_namespace}}.concept_relationship` cr
ON lsc.CONCEPT_CD = cr.concept_id_1 AND cr.relationship_id = 'Maps to'
LEFT JOIN `{{unioned_ehr_namespace}}.concept` c
ON cr.concept_id_2 = c.concept_id
LEFT JOIN `{{unioned_ehr_namespace}}.concept` c1
ON lsc.CONCEPT_CD = c1.concept_id AND c1.standard_concept in ('S', 'C')
LEFT JOIN `{{unioned_ehr_namespace}}.concept` c2
ON lsc.CONCEPT_CD = c2.concept_id AND c2.standard_concept IS NULL
WHERE (FEATURE_NAME in ('PAP_TEST', 'MAMMOGRAPHY', 'PSA_TEST') AND coalesce(cr.concept_id_2, c1.concept_id) != 4203722)
OR FEATURE_NAME not in ('PAP_TEST', 'MAMMOGRAPHY', 'PSA_TEST')
