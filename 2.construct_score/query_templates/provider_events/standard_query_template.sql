SELECT DISTINCT omop.person_id, o_v.visit_concept_id, omop_ext.src_id, omop.{{date_column}} as event_date
FROM `{{omop_namespace}}.{{omop_table}}` omop
JOIN `{{omop_namespace}}.{{omop_table}}_ext` omop_ext
ON omop.{{omop_table_id}} = omop_ext.{{omop_table_id}}
JOIN `{{output_namespace}}.mv_loyalty_score_concepts_with_standard_concepts` ls
ON omop.{{concept_column_name}} = ls.STANDARD_CONCEPT OR omop.{{source_concept_column_name}} = ls.NON_STANDARD_CONCEPT
JOIN `{{omop_namespace}}.{{omop_visit_table}}` o_v
ON omop.visit_occurrence_id = o_v.visit_occurrence_id
WHERE omop.{{date_column}} BETWEEN "{{start_date}}" AND "{{end_date}}"
AND ls.FEATURE_NAME = "{{feature_name}}"
AND ls.DOMAIN_ID = "{{domain_id}}"
AND omop_ext.src_id LIKE '%EHR site%'
