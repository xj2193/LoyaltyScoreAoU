select src_hpo_id, concat('site_', row_number() OVER()) as site_id from 
(select distinct src_hpo_id from `{{EHR_NAMESPACE}}._mapping_person`)