# PostgreSQL 스키마 문서: `public`

생성일시: 2026-07-08 16:43:33

총 테이블 수: 23개

## 목차
- [_prisma_migrations](#_prisma_migrations)
- [ad_accounts](#ad_accounts)
- [ad_keywords](#ad_keywords)
- [ad_performance_daily](#ad_performance_daily)
- [ad_sets](#ad_sets)
- [ads](#ads)
- [automation_jobs](#automation_jobs)
- [business_portfolios](#business_portfolios)
- [campaigns](#campaigns)
- [click_trends](#click_trends)
- [client_info](#client_info)
- [client_members](#client_members)
- [client_sprint_notes](#client_sprint_notes)
- [clients](#clients)
- [ig_accounts](#ig_accounts)
- [ig_carousel_items](#ig_carousel_items)
- [ig_content_insights](#ig_content_insights)
- [ig_contents](#ig_contents)
- [ig_insights_demographics](#ig_insights_demographics)
- [ig_insights_total](#ig_insights_total)
- [ig_organic_insights](#ig_organic_insights)
- [naver_demographics](#naver_demographics)
- [popular_keywords](#popular_keywords)

---

## _prisma_migrations

(예상 행 수: -1)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | character varying(36) | N |  | ✅ |  |
| checksum | character varying(64) | N |  |  |  |
| finished_at | timestamp with time zone | Y |  |  |  |
| migration_name | character varying(255) | N |  |  |  |
| logs | text | Y |  |  |  |
| rolled_back_at | timestamp with time zone | Y |  |  |  |
| started_at | timestamp with time zone | N | now() |  |  |
| applied_steps_count | integer | N | 0 |  |  |

**인덱스:**
- UNIQUE `_prisma_migrations_pkey` (id)

---

## ad_accounts

(예상 행 수: 41)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('ad_accounts_id_seq'::regclass) | ✅ |  |
| business_portfolio_id | bigint | N |  |  |  |
| ig_account_id | bigint | Y |  |  |  |
| fb_ad_account_id | character varying(64) | N |  |  |  |
| name | text | Y |  |  |  |
| currency | character varying(10) | Y |  |  |  |
| account_status | integer | Y |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**외래키(FK):**
- `business_portfolio_id` → `public.business_portfolios.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)
- `ig_account_id` → `public.ig_accounts.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `ad_accounts_fb_ad_account_id_key` (fb_ad_account_id)
- UNIQUE `ad_accounts_pkey` (id)

---

## ad_keywords

(예상 행 수: 7641)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| ad_id | bigint | N |  | ✅ |  |
| essential_keywords | text[] | Y |  |  |  |
| variable_keywords | text[] | Y |  |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**외래키(FK):**
- `ad_id` → `public.ads.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `ad_keywords_pkey` (ad_id)

---

## ad_performance_daily

(예상 행 수: 1427259)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| ad_id | bigint | N |  | ✅ |  |
| age_range | character varying(50) | N |  | ✅ |  |
| gender | character varying(50) | N |  | ✅ |  |
| as_of_date | date | N |  | ✅ |  |
| reach | integer | Y |  |  |  |
| impressions | integer | Y |  |  |  |
| clicks | integer | Y |  |  |  |
| ctr | double precision | Y |  |  |  |
| frequency | double precision | Y |  |  |  |
| spend | double precision | Y |  |  |  |
| purchase_count | integer | Y |  |  |  |
| purchase_value | double precision | Y |  |  |  |
| purchase_roas | double precision | Y |  |  |  |
| goal_conv_count | integer | Y |  |  |  |
| goal_conv_value | double precision | Y |  |  |  |
| goal_conv_cpa | double precision | Y |  |  |  |
| goal_conv_name | text | Y |  |  |  |
| goal_conv_id | character varying(64) | Y |  |  |  |
| cpc | double precision | Y |  |  |  |
| cpm | double precision | Y |  |  |  |
| link_clicks | integer | Y |  |  |  |
| view_content | integer | Y |  |  |  |
| add_to_cart | integer | Y |  |  |  |
| initiate_checkout | integer | Y |  |  |  |
| complete_registration | integer | Y |  |  |  |
| instagram_profile_visits | integer | Y |  |  |  |
| website_landing_page_views | integer | Y |  |  |  |
| inline_post_engagement | integer | Y |  |  |  |
| post_reactions | integer | Y |  |  |  |
| comments | integer | Y |  |  |  |
| post_saves | integer | Y |  |  |  |
| video_views | integer | Y |  |  |  |
| video_p25_watched | integer | Y |  |  |  |
| video_p50_watched | integer | Y |  |  |  |
| video_p75_watched | integer | Y |  |  |  |
| video_p100_watched | integer | Y |  |  |  |
| video_thruplay_watched | integer | Y |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**외래키(FK):**
- `ad_id` → `public.ads.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `ad_performance_daily_pkey` (ad_id, age_range, gender, as_of_date)

---

## ad_sets

(예상 행 수: 5619)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('ad_sets_id_seq'::regclass) | ✅ |  |
| campaign_id | bigint | N |  |  |  |
| fb_ad_set_id | character varying(64) | N |  |  |  |
| ad_set_name | text | Y |  |  |  |
| optimization_goal | character varying(64) | Y |  |  |  |
| billing_event | character varying(64) | Y |  |  |  |
| status | character varying(64) | Y |  |  |  |
| effective_status | character varying(64) | Y |  |  |  |
| targeting_spec | jsonb | Y |  |  |  |
| fb_created_time | timestamp with time zone | N |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**외래키(FK):**
- `campaign_id` → `public.campaigns.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `ad_sets_fb_ad_set_id_key` (fb_ad_set_id)
- UNIQUE `ad_sets_pkey` (id)

---

## ads

(예상 행 수: 9955)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('ads_id_seq'::regclass) | ✅ |  |
| ad_set_id | bigint | N |  |  |  |
| account_id | bigint | N |  |  |  |
| fb_ad_id | character varying(64) | N |  |  |  |
| ad_name | text | Y |  |  |  |
| body | text | Y |  |  |  |
| status | character varying(64) | Y |  |  |  |
| effective_status | character varying(64) | Y |  |  |  |
| source_ig_media_id | character varying(64) | Y |  |  |  |
| landing_page_url | text | Y |  |  |  |
| thumb_link | text | Y |  |  |  |
| fb_created_time | timestamp with time zone | N |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |
| body_embedding | vector(1536) | Y |  |  |  |

**외래키(FK):**
- `ad_set_id` → `public.ad_sets.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)
- `account_id` → `public.ad_accounts.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `ads_fb_ad_id_key` (fb_ad_id)
- UNIQUE `ads_pkey` (id)

---

## automation_jobs

(예상 행 수: -1)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('automation_jobs_id_seq'::regclass) | ✅ |  |
| job_name | character varying(100) | N |  |  |  |
| job_type | character varying(50) | N |  |  |  |
| status | character varying(20) | N |  |  |  |
| start_time | timestamp(6) with time zone | N |  |  |  |
| end_time | timestamp(6) with time zone | Y |  |  |  |
| total_accounts | integer | Y | 0 |  |  |
| processed_accounts | integer | Y | 0 |  |  |
| error_message | text | Y |  |  |  |
| created_at | timestamp(6) with time zone | N | CURRENT_TIMESTAMP |  |  |

**인덱스:**
- UNIQUE `automation_jobs_pkey` (id)
- `idx_automation_jobs_created_at` (created_at)
- `idx_automation_jobs_type_created` (job_type, created_at)

---

## business_portfolios

(예상 행 수: 40)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('business_portfolios_id_seq'::regclass) | ✅ |  |
| client_id | bigint | Y |  |  |  |
| fb_business_id | character varying(64) | N |  |  |  |
| business_name | text | Y |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**외래키(FK):**
- `client_id` → `public.clients.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `business_portfolios_fb_business_id_key` (fb_business_id)
- UNIQUE `business_portfolios_pkey` (id)

---

## campaigns

(예상 행 수: 1423)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('campaigns_id_seq'::regclass) | ✅ |  |
| ad_account_id | bigint | N |  |  |  |
| fb_campaign_id | character varying(64) | N |  |  |  |
| name | text | Y |  |  |  |
| objective | character varying(64) | Y |  |  |  |
| status | character varying(64) | Y |  |  |  |
| effective_status | character varying(64) | Y |  |  |  |
| fb_created_time | timestamp with time zone | N |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**외래키(FK):**
- `ad_account_id` → `public.ad_accounts.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `campaigns_fb_campaign_id_key` (fb_campaign_id)
- UNIQUE `campaigns_pkey` (id)

---

## click_trends

(예상 행 수: -1)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('click_trends_id_seq'::regclass) | ✅ |  |
| client_id | bigint | N |  |  |  |
| period_type | character varying(20) | N |  |  |  |
| period_label | character varying(50) | N |  |  |  |
| trend_date | date | N |  |  |  |
| date_label | character varying(20) | Y |  |  |  |
| click_value | integer | N |  |  |  |
| created_at | timestamp(6) with time zone | N | CURRENT_TIMESTAMP |  |  |
| updated_at | timestamp(6) with time zone | N | CURRENT_TIMESTAMP |  |  |

**외래키(FK):**
- `client_id` → `public.clients.id` (ON UPDATE CASCADE, ON DELETE CASCADE)

**인덱스:**
- UNIQUE `click_trends_client_period_date_key` (client_id, period_type, trend_date)
- UNIQUE `click_trends_pkey` (id)

---

## client_info

(예상 행 수: 35)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| client_id | bigint | N |  | ✅ |  |
| brand_name | text[] | Y |  |  |  |
| init_essential | text[] | Y |  |  |  |

**외래키(FK):**
- `client_id` → `public.clients.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `client_info_pkey` (client_id)

---

## client_members

(예상 행 수: 125)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('client_members_id_seq'::regclass) | ✅ |  |
| client_id | bigint | Y |  |  |  |
| role | character varying(64) | N |  |  |  |
| sub_role | character varying(64) | Y |  |  |  |
| name | text | Y |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**외래키(FK):**
- `client_id` → `public.clients.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `client_members_pkey` (id)

---

## client_sprint_notes

(예상 행 수: 322)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('client_sprint_notes_id_seq'::regclass) | ✅ |  |
| client_id | bigint | N |  |  |  |
| sprint_number | integer | N |  |  |  |
| title | text | Y |  |  |  |
| focus | text | Y |  |  |  |
| objectives | jsonb | Y |  |  |  |
| notes | text | Y |  |  |  |
| tags | text[] | Y |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**인덱스:**
- UNIQUE `client_sprint_notes_pkey` (id)

---

## clients

(예상 행 수: 37)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('clients_id_seq'::regclass) | ✅ |  |
| username | text | N |  |  |  |
| password | text | Y |  |  |  |
| email | text | Y |  |  |  |
| is_admin | boolean | Y | false |  |  |
| is_active | boolean | N | true |  |  |
| last_login_at | timestamp with time zone | Y | now() |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |
| depart_brand_id | bigint | Y |  |  |  |
| sprint_anchor_date | date | Y |  |  |  |
| sprint_anchor_number | integer | N | 1 |  |  |
| categories | character varying(50)[] | Y |  |  |  |
| linkiwi_user_id | bigint | Y |  |  |  |

**인덱스:**
- UNIQUE `clients_pkey` (id)
- UNIQUE `idx_clients_depart_brand_id` (depart_brand_id)
- UNIQUE `idx_clients_linkiwi_user_id` (linkiwi_user_id)

---

## ig_accounts

(예상 행 수: 47)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('ig_accounts_id_seq'::regclass) | ✅ |  |
| business_portfolio_id | bigint | N |  |  |  |
| fb_ig_id | character varying(64) | N |  |  |  |
| username | text | Y |  |  |  |
| is_active | boolean | N | true |  |  |
| connected_at | timestamp with time zone | Y |  |  |  |
| disconnected_at | timestamp with time zone | Y |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**외래키(FK):**
- `business_portfolio_id` → `public.business_portfolios.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `ig_accounts_fb_ig_id_key` (fb_ig_id)
- UNIQUE `ig_accounts_pkey` (id)

---

## ig_carousel_items

(예상 행 수: 30422)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('ig_carousel_items_id_seq'::regclass) | ✅ |  |
| content_id | bigint | N |  |  |  |
| fb_child_media_id | character varying(64) | N |  |  |  |
| sort_order | integer | N |  |  |  |
| child_media_type | text | N |  |  |  |
| child_media_url | text | Y |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**외래키(FK):**
- `content_id` → `public.ig_contents.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `ig_carousel_items_fb_child_media_id_key` (fb_child_media_id)
- UNIQUE `ig_carousel_items_pkey` (id)

---

## ig_content_insights

(예상 행 수: 17793)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| content_id | bigint | N |  | ✅ |  |
| as_of_date | date | N |  | ✅ |  |
| reach | integer | Y |  |  |  |
| likes | integer | Y |  |  |  |
| comments | integer | Y |  |  |  |
| shares | integer | Y |  |  |  |
| saved | integer | Y |  |  |  |
| total_interactions | integer | Y |  |  |  |
| views | integer | Y |  |  |  |
| follows | integer | Y |  |  |  |
| profile_visits | integer | Y |  |  |  |
| profile_activity | integer | Y |  |  |  |
| ig_reels_avg_watch_time | bigint | Y |  |  |  |
| ig_reels_video_view_total_time | bigint | Y |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**외래키(FK):**
- `content_id` → `public.ig_contents.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `ig_content_insights_pkey` (content_id, as_of_date)

---

## ig_contents

(예상 행 수: 8069)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('ig_contents_id_seq'::regclass) | ✅ |  |
| ig_id | bigint | N |  |  |  |
| fb_ig_media_id | character varying(64) | N |  |  |  |
| caption | text | Y |  |  |  |
| ig_media_type | text | N |  |  |  |
| ig_permalink | text | Y |  |  |  |
| ig_timestamp | timestamp with time zone | N |  |  |  |
| media_url | text | Y |  |  |  |
| thumbnail_url | text | Y |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**외래키(FK):**
- `ig_id` → `public.ig_accounts.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `ig_contents_fb_ig_media_id_key` (fb_ig_media_id)
- UNIQUE `ig_contents_pkey` (id)

---

## ig_insights_demographics

(예상 행 수: 44479)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| ig_id | bigint | N |  | ✅ |  |
| age_range | character varying(50) | N |  | ✅ |  |
| gender | character varying(50) | N |  | ✅ |  |
| as_of_date | date | N |  | ✅ |  |
| followers | integer | Y |  |  |  |
| engaged_audience | integer | Y |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**외래키(FK):**
- `ig_id` → `public.ig_accounts.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `ig_insights_demographics_pkey` (ig_id, age_range, gender, as_of_date)

---

## ig_insights_total

(예상 행 수: 950)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| ig_id | bigint | N |  | ✅ |  |
| as_of_date | date | N |  | ✅ |  |
| total_reach | integer | Y |  |  |  |
| reach_ad | integer | Y |  |  |  |
| reach_post | integer | Y |  |  |  |
| reach_carousel_container | integer | Y |  |  |  |
| reach_carousel_item | integer | Y |  |  |  |
| reach_reel | integer | Y |  |  |  |
| reach_story | integer | Y |  |  |  |
| reach_follower | integer | Y |  |  |  |
| reach_non_follower | integer | Y |  |  |  |
| reach_follow_unknown | integer | Y |  |  |  |
| total_views | integer | Y |  |  |  |
| views_ad | integer | Y |  |  |  |
| views_post | integer | Y |  |  |  |
| views_carousel_container | integer | Y |  |  |  |
| views_carousel_item | integer | Y |  |  |  |
| views_reel | integer | Y |  |  |  |
| views_story | integer | Y |  |  |  |
| views_follower | integer | Y |  |  |  |
| views_non_follower | integer | Y |  |  |  |
| views_follow_unknown | integer | Y |  |  |  |
| followers_count | integer | Y |  |  |  |
| follows | integer | Y |  |  |  |
| unfollows | integer | Y |  |  |  |
| profile_views | integer | Y |  |  |  |
| total_interactions | integer | Y |  |  |  |
| likes | integer | Y |  |  |  |
| comments | integer | Y |  |  |  |
| shares | integer | Y |  |  |  |
| saves | integer | Y |  |  |  |
| replies | integer | Y |  |  |  |
| reposts | integer | Y |  |  |  |
| profile_links_taps | integer | Y |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**외래키(FK):**
- `ig_id` → `public.ig_accounts.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `ig_insights_total_pkey` (ig_id, as_of_date)

---

## ig_organic_insights

(예상 행 수: 677)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| ig_id | bigint | N |  | ✅ |  |
| date_start | date | N |  | ✅ |  |
| date_end | date | N |  | ✅ |  |
| organic_views | integer | Y |  |  |  |
| created_at | timestamp with time zone | N | now() |  |  |
| updated_at | timestamp with time zone | N | now() |  |  |

**외래키(FK):**
- `ig_id` → `public.ig_accounts.id` (ON UPDATE NO ACTION, ON DELETE NO ACTION)

**인덱스:**
- UNIQUE `ig_organic_insights_pkey` (ig_id, date_start, date_end)

---

## naver_demographics

(예상 행 수: -1)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('naver_demographics_id_seq'::regclass) | ✅ |  |
| client_id | bigint | N |  |  |  |
| period_type | character varying(20) | N |  |  |  |
| period_label | character varying(50) | N |  |  |  |
| base_date | date | N |  |  |  |
| female_per | numeric(5,2) | Y |  |  |  |
| male_per | numeric(5,2) | Y |  |  |  |
| top_age_1 | character varying(20) | Y |  |  |  |
| top_age_2 | character varying(20) | Y |  |  |  |
| created_at | timestamp(6) with time zone | N | CURRENT_TIMESTAMP |  |  |
| updated_at | timestamp(6) with time zone | N | CURRENT_TIMESTAMP |  |  |

**외래키(FK):**
- `client_id` → `public.clients.id` (ON UPDATE CASCADE, ON DELETE CASCADE)

**인덱스:**
- UNIQUE `naver_demographics_client_period_base_key` (client_id, period_type, base_date)
- UNIQUE `naver_demographics_pkey` (id)

---

## popular_keywords

(예상 행 수: -1)

| 컬럼명 | 타입 | Nullable | 기본값 | PK | 설명 |
|---|---|---|---|---|---|
| id | bigint | N | nextval('popular_keywords_id_seq'::regclass) | ✅ |  |
| client_id | bigint | N |  |  |  |
| period_type | character varying(20) | N |  |  |  |
| period_label | character varying(50) | N |  |  |  |
| base_date | date | N |  |  |  |
| rank | integer | N |  |  |  |
| keyword | character varying(100) | N |  |  |  |
| prev_rank | integer | Y |  |  |  |
| created_at | timestamp(6) with time zone | N | CURRENT_TIMESTAMP |  |  |
| updated_at | timestamp(6) with time zone | N | CURRENT_TIMESTAMP |  |  |

**외래키(FK):**
- `client_id` → `public.clients.id` (ON UPDATE CASCADE, ON DELETE CASCADE)

**인덱스:**
- UNIQUE `popular_keywords_client_period_base_rank_key` (client_id, period_type, base_date, rank)
- UNIQUE `popular_keywords_pkey` (id)

---
