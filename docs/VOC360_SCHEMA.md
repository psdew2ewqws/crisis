# voc360 — Data Source Schema (read-only)

VOC360 DATABASE (PostgreSQL 16 @ <VOC_HOST>:5432/voc360, sslmode=require, READ-ONLY) — a live Voice-of-Customer 360 platform for Jordanian public services. This is the DATA SOURCE the system connects cases to.

THE DATA -> GRAPH -> ROOT-CAUSE CHAIN (real tables):
- the_data (22,882 rows) = the SIGNAL / data-source layer. Cols: record_id, source_record_id, source_type (app_review 18.6k, social_media_sentiment 1.6k, employee_complaint, qr/ces/csat_survey, complaint, + Arabic types فساد_إداري/admin-corruption, سوء_الخدمة/poor-service, عدم_الرد/no-response), source_platform, source_channel, entity_id, service_id (Sanad 15.8k, Amman Bus 2k, Bekhedmetkom, نقل_عام/transit, طرق_وبنية_تحتية/roads, مراكز_الخدمة, جوازات_السفر/passports, الخدمات_الإلكترونية, ...), governorate (mostly NULL; some الزرقاء/Zarqa, إربد/Irbid, العقبة/Aqaba, السلط/Salt, المفرق, جرش), district, text/text_clean (Arabic), observed_at/date/hour/day_of_week/is_weekend/is_ramadan, rating, signal_value, sentiment_label (negative/positive/neutral_citizen_sentiment, high_severity_complaint), confidence, severity (low 2258/medium 786/high 812/critical 395; null for app_reviews), duplicate_flag, spam_flag.
- ril_text_segments (2,001) = extracted problem segments. Cols: segment_id, record_id, segment_text, segment_type('problem'), confidence, language('ar'), embedding_vector (text json array), metadata_json. NOTE: record_id does NOT join to the_data ids (RIL ran on a separate snapshot) — treat the two layers as parallel for now.
- ril_cluster_members (903) = segment_id -> cluster_id (+ distance_to_centroid).
- ril_problem_clusters (21; 20 with members) = the ROOT-CAUSE layer. Cols: cluster_id, canonical_label_ar (REAL Arabic problem text, e.g. تأخير دعم صندوق المعونة/National-Aid-Fund delays, الباص السريع/BRT bus, رسوم الخدمة المستعجلة/urgent-service fees, منصة تكافل/Takaful platform), canonical_label_en, description, parent_cluster_id (hierarchy field; currently flat NULL), entity_id, service_id, member_count (top: 551,69,64,55,52,23,18,9,9,9,8,7), severity_avg, centroid_vector (embedding), status('active'), first_seen/last_seen.
- Also: pm_gam_calls (126k municipality call logs), pm_bkhidmatkom_complaints (4k), pm_mol_complaints (MoL), pm_moh_complaints (MoH), social_sentiment_signals/telegram/tiktok, google_review_data, youtube_data, pm_surveys, pm_kpi_summary, forecast_questions, jordan_public.

THE LIVE GRAPH to build from this:
  Source(source_type) --count--> Service(service_id) --count--> Governorate ; each signal carries severity+sentiment.
  Segment --member_of--> ProblemCluster --part_of--> parent (root-cause tree).
  ROOT CAUSE = dominant ProblemCluster(s) (by member_count x severity_avg) behind a service's complaints.
A CASE = a service / governorate / emerging problem cluster. The flow: connect to DB -> pull signals -> build graph -> rank root-cause clusters -> recommend. The system must do this LIVE and render a visual graph.
