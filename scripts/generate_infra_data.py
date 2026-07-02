import csv, os, random
from collections import defaultdict, deque

random.seed(42)

# =============================================================================
# NODE DEFINITIONS
# 90 nodes across 7 tiers
# Tier assignments honor fan-out design:
#   Edge/Perimeter (6), Application/Service (28), Data (18),
#   Infrastructure (14), External Dependency (10),
#   Core Business Systems (8), Monitoring/Ops (6)
# =============================================================================

nodes = [

  # ── TIER: Edge / Perimeter (6) ─────────────────────────────────────────────
  # All inbound traffic enters here. CDN and WAF are fully upstream.
  # Auth-gateway is the planted SPOF (Risk #1): no redundant path,
  # every authenticated request passes through it.
  {"id":"cdn",             "name":"CDN / Edge Cache",           "tier":"Edge / Perimeter",      "business_function":"Static asset delivery and DDoS mitigation",                         "revenue_weight":2, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"waf",             "name":"Web Application Firewall",   "tier":"Edge / Perimeter",      "business_function":"Layer-7 threat filtering for all inbound HTTP traffic",              "revenue_weight":3, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"lb-primary",      "name":"Primary Load Balancer",      "tier":"Edge / Perimeter",      "business_function":"Traffic distribution across application tier",                       "revenue_weight":3, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"lb-secondary",    "name":"Secondary Load Balancer",    "tier":"Edge / Perimeter",      "business_function":"Failover load balancer — partial traffic coverage only",             "revenue_weight":2, "customer_facing":True,  "redundant":False, "spof":False, "risk_node":False},
  {"id":"auth-gateway",    "name":"Authentication Gateway",     "tier":"Edge / Perimeter",      "business_function":"Central authentication and session management for all services",    "revenue_weight":5, "customer_facing":True,  "redundant":False, "spof":True,  "risk_node":True},
  {"id":"api-gateway",     "name":"API Gateway",                "tier":"Edge / Perimeter",      "business_function":"External API routing, rate limiting, and developer portal",         "revenue_weight":3, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},

  # ── TIER: Core Business Systems (8) ────────────────────────────────────────
  # These are the ultimate consumers most application services serve.
  # Core-ledger is the planted SPOF (Risk #2): single primary,
  # read by nearly every financial service.
  {"id":"core-ledger",     "name":"Core Financial Ledger",      "tier":"Core Business Systems", "business_function":"Authoritative source of record for all financial transactions",      "revenue_weight":5, "customer_facing":False, "redundant":False, "spof":True,  "risk_node":True},
  {"id":"billing-legacy",  "name":"Legacy Billing Service",     "tier":"Core Business Systems", "business_function":"Payment reconciliation and invoice generation — pre-migration system","revenue_weight":5, "customer_facing":False, "redundant":False, "spof":True,  "risk_node":True},
  {"id":"customer-portal", "name":"Customer Portal",            "tier":"Core Business Systems", "business_function":"Primary customer-facing web and mobile application",                 "revenue_weight":5, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"compliance-rpt",  "name":"Regulatory Reporting Engine","tier":"Core Business Systems", "business_function":"Automated generation of MiFID II, EMIR, and DORA submissions",      "revenue_weight":3, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"risk-engine",     "name":"Real-Time Risk Engine",      "tier":"Core Business Systems", "business_function":"Pre-trade risk checks and position limit enforcement",               "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"onboarding-svc",  "name":"Client Onboarding Service",  "tier":"Core Business Systems", "business_function":"New client KYC workflow orchestration and account activation",      "revenue_weight":3, "customer_facing":True,  "redundant":False, "spof":False, "risk_node":False},
  {"id":"treasury-svc",    "name":"Treasury Management Service","tier":"Core Business Systems", "business_function":"Cash position management and intraday liquidity tracking",          "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"audit-trail",     "name":"Audit Trail Service",        "tier":"Core Business Systems", "business_function":"Immutable event log for all system and user actions",               "revenue_weight":3, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},

  # ── TIER: Application / Service (28) ───────────────────────────────────────
  # Microservices layer. Mix of customer-facing, internal, and batch.
  # billing-legacy (above) is the planted betweenness chokepoint (Risk #3)
  # for reconciliation paths — all payment services call it.
  {"id":"payment-svc",     "name":"Payment Processing Service", "tier":"Application / Service", "business_function":"Real-time payment initiation and routing",                          "revenue_weight":5, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"payment-svc-b",   "name":"Payment Processing (Backup)","tier":"Application / Service", "business_function":"Secondary payment processor — overflow and failover only",          "revenue_weight":3, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"fx-svc",          "name":"FX Conversion Service",      "tier":"Application / Service", "business_function":"Real-time foreign exchange rate application and conversion",        "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"account-svc",     "name":"Account Management Service", "tier":"Application / Service", "business_function":"Account lifecycle, balance enquiry, and statement generation",     "revenue_weight":4, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"notification-svc","name":"Notification Service",       "tier":"Application / Service", "business_function":"Email, SMS, and push notification dispatch",                       "revenue_weight":2, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"search-svc",      "name":"Transaction Search Service", "tier":"Application / Service", "business_function":"Full-text and faceted search over transaction history",             "revenue_weight":2, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"reporting-svc",   "name":"Client Reporting Service",   "tier":"Application / Service", "business_function":"Scheduled and on-demand client statement generation",              "revenue_weight":3, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"fraud-svc",       "name":"Fraud Detection Service",    "tier":"Application / Service", "business_function":"Real-time transaction scoring and fraud signal aggregation",        "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"limits-svc",      "name":"Limits & Controls Service",  "tier":"Application / Service", "business_function":"Velocity limits, daily caps, and sanction screening pre-checks",   "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"pricing-svc",     "name":"Pricing Service",            "tier":"Application / Service", "business_function":"Real-time fee calculation and tariff application",                 "revenue_weight":3, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"consent-svc",     "name":"Consent & Preferences Svc",  "tier":"Application / Service", "business_function":"Customer consent records and communication preferences",           "revenue_weight":2, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"doc-svc",         "name":"Document Management Service","tier":"Application / Service", "business_function":"Contract storage, retrieval, and e-signature orchestration",       "revenue_weight":2, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"scheduler-svc",   "name":"Batch Scheduler",            "tier":"Application / Service", "business_function":"Cron-based orchestration for overnight batch jobs",                "revenue_weight":2, "customer_facing":False, "redundant":False, "spof":False, "risk_node":False},
  {"id":"recon-svc",       "name":"Reconciliation Service",     "tier":"Application / Service", "business_function":"End-of-day position and cash reconciliation",                     "revenue_weight":4, "customer_facing":False, "redundant":False, "spof":False, "risk_node":False},
  {"id":"interest-svc",    "name":"Interest Accrual Service",   "tier":"Application / Service", "business_function":"Daily interest calculation and posting to ledger",                 "revenue_weight":3, "customer_facing":False, "redundant":False, "spof":False, "risk_node":False},
  {"id":"position-svc",    "name":"Position Management Service","tier":"Application / Service", "business_function":"Real-time portfolio position calculation and aggregation",         "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"order-svc",       "name":"Order Management Service",   "tier":"Application / Service", "business_function":"Order lifecycle management from submission to settlement",         "revenue_weight":4, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"settlement-svc",  "name":"Settlement Service",         "tier":"Application / Service", "business_function":"Trade settlement instruction generation and tracking",             "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"margin-svc",      "name":"Margin Calculation Service", "tier":"Application / Service", "business_function":"Initial and variation margin calculation for derivatives",         "revenue_weight":3, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"fee-svc",         "name":"Fee Management Service",     "tier":"Application / Service", "business_function":"Fee accrual, adjustment, and billing instruction generation",      "revenue_weight":3, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"entitlement-svc", "name":"Entitlements Service",       "tier":"Application / Service", "business_function":"User and API permission management downstream of auth-gateway",    "revenue_weight":3, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"profile-svc",     "name":"Client Profile Service",     "tier":"Application / Service", "business_function":"Customer master data — demographics, preferences, tier",           "revenue_weight":3, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"workflow-svc",    "name":"Workflow Orchestration Svc", "tier":"Application / Service", "business_function":"Multi-step business process automation (onboarding, disputes)",    "revenue_weight":3, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"config-svc",      "name":"Config Service",             "tier":"Application / Service", "business_function":"Centralised runtime configuration and feature flag management",    "revenue_weight":2, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"analytics-svc",   "name":"Internal Analytics Service", "tier":"Application / Service", "business_function":"Business intelligence aggregation and management dashboard data",  "revenue_weight":1, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"healthcheck-svc", "name":"Health Check Aggregator",    "tier":"Application / Service", "business_function":"Synthetic monitoring and dependency liveness checks",              "revenue_weight":1, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"rate-limit-svc",  "name":"Rate Limiting Service",      "tier":"Application / Service", "business_function":"Per-client API quota enforcement",                                "revenue_weight":2, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"export-svc",      "name":"Data Export Service",        "tier":"Application / Service", "business_function":"Bulk data export for client integrations and regulatory feeds",    "revenue_weight":2, "customer_facing":True,  "redundant":False, "spof":False, "risk_node":False},
  {"id":"dispute-svc",     "name":"Dispute Management Service", "tier":"Application / Service", "business_function":"Payment dispute intake, workflow, and resolution tracking",        "revenue_weight":2, "customer_facing":True,  "redundant":False, "spof":False, "risk_node":False},

  # ── TIER: Data (18) ────────────────────────────────────────────────────────
  # core-ledger-db is Risk #2. message-queue is Risk #4 (planted:
  # 12+ services depend on it, no partitioning by criticality).
  # secrets-vault is Risk #6 (PageRank SPOF via transitive dependency).
  {"id":"core-ledger-db",  "name":"Core Ledger Database",       "tier":"Data",                  "business_function":"Primary Postgres — financial transactions, double-entry ledger",    "revenue_weight":5, "customer_facing":False, "redundant":False, "spof":True,  "risk_node":True},
  {"id":"customer-db",     "name":"Customer Identity Database", "tier":"Data",                  "business_function":"Customer master data, authentication credentials, KYC status",     "revenue_weight":5, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"transaction-db",  "name":"Transaction History Database","tier":"Data",                 "business_function":"Append-only transaction history store — read-optimised replica",   "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"message-queue",   "name":"Shared Message Queue",       "tier":"Data",                  "business_function":"Central Kafka cluster — 12+ services, no criticality partitioning", "revenue_weight":5, "customer_facing":False, "redundant":False, "spof":True,  "risk_node":True},
  {"id":"cache-primary",   "name":"Primary Cache Cluster",      "tier":"Data",                  "business_function":"Redis cluster — session state, rate-limit counters, hot data",      "revenue_weight":3, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"cache-secondary", "name":"Secondary Cache Cluster",    "tier":"Data",                  "business_function":"Fallback Redis — activated on primary failure, partial coverage",   "revenue_weight":2, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"secrets-vault",   "name":"Secrets Vault",              "tier":"Data",                  "business_function":"HashiCorp Vault — all service-to-DB credentials and API keys",     "revenue_weight":5, "customer_facing":False, "redundant":False, "spof":True,  "risk_node":True},
  {"id":"object-store",    "name":"Object Storage",             "tier":"Data",                  "business_function":"S3-compatible store for documents, exports, and audit archives",    "revenue_weight":2, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"search-index",    "name":"Search Index",               "tier":"Data",                  "business_function":"Elasticsearch cluster for transaction search and log aggregation",  "revenue_weight":2, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"analytics-db",    "name":"Analytics Data Warehouse",   "tier":"Data",                  "business_function":"Columnar store for BI queries and management reporting",            "revenue_weight":1, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"config-db",       "name":"Config Database",            "tier":"Data",                  "business_function":"Persistent store for runtime configuration and feature flags",      "revenue_weight":2, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"audit-db",        "name":"Audit Database",             "tier":"Data",                  "business_function":"Immutable append-only store for all audit events",                 "revenue_weight":3, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"position-db",     "name":"Position Database",          "tier":"Data",                  "business_function":"Real-time position snapshots and historical position store",        "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"reporting-db",    "name":"Reporting Database",         "tier":"Data",                  "business_function":"Denormalised read replica optimised for client reporting queries",  "revenue_weight":3, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"dlq",             "name":"Dead Letter Queue",          "tier":"Data",                  "business_function":"Failed message capture for retry and alerting",                    "revenue_weight":1, "customer_facing":False, "redundant":False, "spof":False, "risk_node":False},
  {"id":"timeseries-db",   "name":"Time-Series Database",       "tier":"Data",                  "business_function":"InfluxDB — metrics, latency traces, and infrastructure telemetry", "revenue_weight":1, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"consent-db",      "name":"Consent Database",           "tier":"Data",                  "business_function":"Persistent consent records and GDPR preference store",             "revenue_weight":2, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"workflow-db",     "name":"Workflow State Database",    "tier":"Data",                  "business_function":"Durable workflow state for long-running business processes",        "revenue_weight":2, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},

  # ── TIER: Infrastructure (14) ──────────────────────────────────────────────
  {"id":"k8s-prod",        "name":"Production K8s Cluster",     "tier":"Infrastructure",        "business_function":"Primary container orchestration for all production workloads",      "revenue_weight":5, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"k8s-data",        "name":"Data Plane K8s Cluster",     "tier":"Infrastructure",        "business_function":"Isolated cluster for stateful data-tier workloads",                "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"service-mesh",    "name":"Service Mesh Control Plane", "tier":"Infrastructure",        "business_function":"mTLS, traffic policy, and observability for all east-west traffic", "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"dns-internal",    "name":"Internal DNS",               "tier":"Infrastructure",        "business_function":"Service discovery and internal name resolution",                    "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"network-prod",    "name":"Production Network Segment", "tier":"Infrastructure",        "business_function":"Core VPC — production application and data tier subnets",           "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"network-mgmt",    "name":"Management Network Segment", "tier":"Infrastructure",        "business_function":"Out-of-band management plane for infrastructure administration",    "revenue_weight":2, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"vm-batch",        "name":"Batch VM Pool",              "tier":"Infrastructure",        "business_function":"Dedicated VM pool for overnight batch and scheduled jobs",          "revenue_weight":2, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"vm-ml",           "name":"ML Inference VM Pool",       "tier":"Infrastructure",        "business_function":"GPU-enabled pool for fraud model inference and risk scoring",       "revenue_weight":3, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"vpn-gateway",     "name":"VPN Gateway",                "tier":"Infrastructure",        "business_function":"Remote access VPN for engineering and operations staff",            "revenue_weight":1, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"hsm",             "name":"Hardware Security Module",   "tier":"Infrastructure",        "business_function":"Key management and cryptographic operations for payment signing",   "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"cdn-origin",      "name":"CDN Origin Server",          "tier":"Infrastructure",        "business_function":"Origin server pool backing the edge CDN layer",                    "revenue_weight":3, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"bastion",         "name":"Bastion Host",               "tier":"Infrastructure",        "business_function":"Hardened SSH jump host for infrastructure access",                  "revenue_weight":1, "customer_facing":False, "redundant":False, "spof":False, "risk_node":False},
  {"id":"cert-mgr",        "name":"Certificate Manager",        "tier":"Infrastructure",        "business_function":"TLS certificate provisioning and auto-renewal",                    "revenue_weight":3, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"firewall",        "name":"Network Firewall",           "tier":"Infrastructure",        "business_function":"East-west traffic filtering between production network segments",   "revenue_weight":3, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},

  # ── TIER: External Dependency (10) ─────────────────────────────────────────
  # kyc-vendor is Risk #5: low centrality, high blast radius.
  # No circuit breaker or cached fallback.
  {"id":"kyc-vendor",      "name":"KYC / AML Vendor API",       "tier":"External Dependency",   "business_function":"Real-time identity verification and AML screening — no fallback",   "revenue_weight":4, "customer_facing":False, "redundant":False, "spof":False, "risk_node":True},
  {"id":"payment-network", "name":"Payment Network (SEPA/SWIFT)","tier":"External Dependency",  "business_function":"Interbank payment instruction submission and status polling",        "revenue_weight":5, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"market-data",     "name":"Market Data Feed",           "tier":"External Dependency",   "business_function":"Real-time FX rates, benchmark rates, and reference data",           "revenue_weight":4, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"email-provider",  "name":"Email Delivery Provider",    "tier":"External Dependency",   "business_function":"Transactional email delivery (SendGrid or equivalent)",             "revenue_weight":2, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"sms-provider",    "name":"SMS / OTP Provider",         "tier":"External Dependency",   "business_function":"SMS delivery for OTP, transaction alerts, and 2FA",                "revenue_weight":3, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"custodian-api",   "name":"Custodian Bank API",         "tier":"External Dependency",   "business_function":"Asset custody instructions and settlement confirmation feed",       "revenue_weight":4, "customer_facing":False, "redundant":False, "spof":False, "risk_node":False},
  {"id":"regulator-api",   "name":"Regulatory Reporting API",   "tier":"External Dependency",   "business_function":"Direct submission endpoint for ESMA and national regulator feeds",  "revenue_weight":3, "customer_facing":False, "redundant":False, "spof":False, "risk_node":False},
  {"id":"credit-bureau",   "name":"Credit Bureau API",          "tier":"External Dependency",   "business_function":"Credit score and bureau data for credit decisioning",               "revenue_weight":2, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"psd2-api",        "name":"PSD2 / Open Banking API",    "tier":"External Dependency",   "business_function":"Open Banking account information and payment initiation services",  "revenue_weight":3, "customer_facing":True,  "redundant":True,  "spof":False, "risk_node":False},
  {"id":"cloud-iam",       "name":"Cloud IAM Provider",         "tier":"External Dependency",   "business_function":"External identity federation for staff and partner SSO",            "revenue_weight":2, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},

  # ── TIER: Monitoring / Ops (6) ─────────────────────────────────────────────
  {"id":"log-aggregator",  "name":"Log Aggregator",             "tier":"Monitoring / Ops",      "business_function":"Centralised log collection and SIEM forwarding",                    "revenue_weight":2, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"metrics-platform","name":"Metrics Platform",           "tier":"Monitoring / Ops",      "business_function":"Time-series metrics collection, alerting, and dashboards",          "revenue_weight":2, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"cicd-pipeline",   "name":"CI / CD Pipeline",           "tier":"Monitoring / Ops",      "business_function":"Build, test, and deployment automation for all services",           "revenue_weight":1, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
  {"id":"backup-orch",     "name":"Backup Orchestrator",        "tier":"Monitoring / Ops",      "business_function":"Scheduled backup coordination for all stateful data nodes",         "revenue_weight":2, "customer_facing":False, "redundant":False, "spof":False, "risk_node":False},
  {"id":"incident-mgmt",   "name":"Incident Management System", "tier":"Monitoring / Ops",      "business_function":"PagerDuty-equivalent alerting, on-call routing, and runbooks",      "revenue_weight":1, "customer_facing":False, "redundant":True,  "spof":False, "risk_node":False},
]

assert len(nodes) == 90, f"Node count: {len(nodes)}"

# =============================================================================
# EDGE DEFINITIONS  (from -> to means "from depends on to")
# Designed to produce:
#   Risk 1  auth-gateway: high betweenness (all auth paths through it)
#   Risk 2  core-ledger-db: high eigenvector + PageRank (many high-value deps)
#   Risk 3  billing-legacy: high betweenness (all reconciliation paths)
#   Risk 4  message-queue: high betweenness + eigenvector (12+ services)
#   Risk 5  kyc-vendor: low centrality, high blast radius on simulation
#   Risk 6  secrets-vault: high PageRank (transitive dependency for every DB)
# =============================================================================

edges = [

  # ── Edge / Perimeter internal dependencies ─────────────────────────────────
  ("cdn",             "waf"),
  ("waf",             "lb-primary"),
  ("waf",             "lb-secondary"),
  ("lb-primary",      "auth-gateway"),
  ("lb-secondary",    "auth-gateway"),        # both LBs converge on the single auth-gateway
  ("auth-gateway",    "api-gateway"),
  ("auth-gateway",    "entitlement-svc"),
  ("api-gateway",     "rate-limit-svc"),

  # ── auth-gateway fan-out: every authenticated service depends on it ─────────
  # This is what makes auth-gateway a betweenness chokepoint
  ("auth-gateway",    "payment-svc"),
  ("auth-gateway",    "account-svc"),
  ("auth-gateway",    "order-svc"),
  ("auth-gateway",    "customer-portal"),
  ("auth-gateway",    "onboarding-svc"),
  ("auth-gateway",    "fx-svc"),
  ("auth-gateway",    "position-svc"),
  ("auth-gateway",    "reporting-svc"),
  ("auth-gateway",    "consent-svc"),
  ("auth-gateway",    "doc-svc"),
  ("auth-gateway",    "dispute-svc"),
  ("auth-gateway",    "psd2-api"),

  # ── Application layer → Core business systems ─────────────────────────────
  ("payment-svc",     "billing-legacy"),      # Risk 3: payment goes through legacy billing
  ("payment-svc-b",   "billing-legacy"),      # backup payment also routes through billing
  ("recon-svc",       "billing-legacy"),
  ("fee-svc",         "billing-legacy"),
  ("interest-svc",    "billing-legacy"),
  ("settlement-svc",  "billing-legacy"),

  ("payment-svc",     "core-ledger"),
  ("fx-svc",          "core-ledger"),
  ("account-svc",     "core-ledger"),
  ("recon-svc",       "core-ledger"),
  ("treasury-svc",    "core-ledger"),
  ("interest-svc",    "core-ledger"),
  ("margin-svc",      "core-ledger"),
  ("fee-svc",         "core-ledger"),
  ("settlement-svc",  "core-ledger"),
  ("position-svc",    "core-ledger"),

  ("billing-legacy",  "core-ledger"),         # billing posts to the ledger
  ("core-ledger",     "core-ledger-db"),

  ("order-svc",       "risk-engine"),
  ("payment-svc",     "risk-engine"),
  ("margin-svc",      "risk-engine"),
  ("fraud-svc",       "risk-engine"),
  ("risk-engine",     "limits-svc"),

  ("compliance-rpt",  "audit-trail"),
  ("recon-svc",       "audit-trail"),
  ("order-svc",       "audit-trail"),
  ("payment-svc",     "audit-trail"),
  ("audit-trail",     "audit-db"),

  ("customer-portal", "account-svc"),
  ("customer-portal", "notification-svc"),
  ("customer-portal", "search-svc"),
  ("customer-portal", "reporting-svc"),
  ("customer-portal", "consent-svc"),
  ("customer-portal", "doc-svc"),
  ("customer-portal", "dispute-svc"),

  # ── Application → Data layer ───────────────────────────────────────────────
  # Every service authenticates to its DB via secrets-vault (Risk 6)
  ("account-svc",     "customer-db"),
  ("profile-svc",     "customer-db"),
  ("onboarding-svc",  "customer-db"),
  ("consent-svc",     "consent-db"),
  ("consent-svc",     "customer-db"),

  ("search-svc",      "search-index"),
  ("search-svc",      "transaction-db"),
  ("reporting-svc",   "reporting-db"),
  ("reporting-svc",   "transaction-db"),
  ("analytics-svc",   "analytics-db"),
  ("analytics-svc",   "transaction-db"),
  ("export-svc",      "transaction-db"),
  ("export-svc",      "object-store"),

  ("position-svc",    "position-db"),
  ("order-svc",       "position-db"),
  ("margin-svc",      "position-db"),
  ("settlement-svc",  "transaction-db"),

  ("workflow-svc",    "workflow-db"),
  ("workflow-svc",    "message-queue"),
  ("onboarding-svc",  "workflow-svc"),
  ("dispute-svc",     "workflow-svc"),

  ("doc-svc",         "object-store"),
  ("doc-svc",         "workflow-db"),

  ("config-svc",      "config-db"),
  ("scheduler-svc",   "config-db"),

  # ── message-queue fan-in: 12+ services publish/subscribe (Risk 4) ──────────
  ("payment-svc",     "message-queue"),
  ("payment-svc-b",   "message-queue"),
  ("account-svc",     "message-queue"),
  ("notification-svc","message-queue"),
  ("fraud-svc",       "message-queue"),
  ("order-svc",       "message-queue"),
  ("settlement-svc",  "message-queue"),
  ("recon-svc",       "message-queue"),
  ("compliance-rpt",  "message-queue"),
  ("audit-trail",     "message-queue"),
  ("risk-engine",     "message-queue"),
  ("position-svc",    "message-queue"),
  ("fee-svc",         "message-queue"),
  ("limits-svc",      "message-queue"),
  ("message-queue",   "dlq"),              # failures route to dead letter queue

  # ── secrets-vault: every service authenticates DB access through it (Risk 6)
  ("core-ledger-db",  "secrets-vault"),
  ("customer-db",     "secrets-vault"),
  ("transaction-db",  "secrets-vault"),
  ("position-db",     "secrets-vault"),
  ("reporting-db",    "secrets-vault"),
  ("consent-db",      "secrets-vault"),
  ("workflow-db",     "secrets-vault"),
  ("config-db",       "secrets-vault"),
  ("audit-db",        "secrets-vault"),
  ("analytics-db",    "secrets-vault"),
  ("cache-primary",   "secrets-vault"),

  # ── Infrastructure dependencies ────────────────────────────────────────────
  ("k8s-prod",        "network-prod"),
  ("k8s-prod",        "dns-internal"),
  ("k8s-prod",        "service-mesh"),
  ("k8s-data",        "network-prod"),
  ("k8s-data",        "dns-internal"),
  ("service-mesh",    "cert-mgr"),
  ("service-mesh",    "secrets-vault"),    # service-mesh pulls certs from vault
  ("network-prod",    "firewall"),
  ("network-mgmt",    "bastion"),
  ("network-mgmt",    "vpn-gateway"),
  ("vpn-gateway",     "bastion"),
  ("payment-svc",     "hsm"),             # payment signing via HSM
  ("settlement-svc",  "hsm"),
  ("cdn",             "cdn-origin"),
  ("cdn-origin",      "k8s-prod"),
  ("vm-batch",        "k8s-prod"),
  ("vm-ml",           "k8s-prod"),
  ("fraud-svc",       "vm-ml"),           # ML inference on GPU pool

  # ── External dependency edges ─────────────────────────────────────────────
  ("payment-svc",     "payment-network"),
  ("settlement-svc",  "payment-network"),
  ("payment-svc",     "custodian-api"),
  ("settlement-svc",  "custodian-api"),
  ("onboarding-svc",  "kyc-vendor"),       # Risk 5: onboarding blocks on KYC
  ("compliance-rpt",  "kyc-vendor"),       # compliance checks also block on KYC
  ("fraud-svc",       "kyc-vendor"),       # fraud screening calls KYC vendor
  ("fx-svc",          "market-data"),
  ("pricing-svc",     "market-data"),
  ("risk-engine",     "market-data"),
  ("margin-svc",      "market-data"),
  ("notification-svc","email-provider"),
  ("notification-svc","sms-provider"),
  ("compliance-rpt",  "regulator-api"),
  ("customer-portal", "psd2-api"),
  ("onboarding-svc",  "credit-bureau"),
  ("cloud-iam",       "auth-gateway"),     # cloud IAM federates into auth-gateway
  ("auth-gateway",    "cloud-iam"),        # and auth-gateway calls cloud IAM for federation

  # ── Monitoring / Ops ──────────────────────────────────────────────────────
  ("log-aggregator",  "timeseries-db"),
  ("metrics-platform","timeseries-db"),
  ("backup-orch",     "object-store"),
  ("healthcheck-svc", "metrics-platform"),
  ("incident-mgmt",   "metrics-platform"),
  ("cicd-pipeline",   "k8s-prod"),
  ("cicd-pipeline",   "secrets-vault"),    # CI/CD pulls deploy secrets from vault

  # Cache dependencies
  ("payment-svc",     "cache-primary"),
  ("auth-gateway",    "cache-primary"),
  ("fraud-svc",       "cache-primary"),
  ("rate-limit-svc",  "cache-primary"),
  ("account-svc",     "cache-primary"),
  ("cache-primary",   "cache-secondary"),  # secondary is the fallback
]

# =============================================================================
# WRITE CSVs
# =============================================================================
os.makedirs("/home/claude/nexacore_blast_radius/data", exist_ok=True)

node_fields = ["id","name","tier","business_function",
               "revenue_weight","customer_facing","redundant","spof","risk_node"]

with open("/home/claude/nexacore_blast_radius/data/nodes.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=node_fields)
    w.writeheader()
    w.writerows(nodes)

edge_rows = [{"from":e[0],"to":e[1]} for e in edges]
with open("/home/claude/nexacore_blast_radius/data/edges.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=["from","to"])
    w.writeheader()
    w.writerows(edge_rows)

# =============================================================================
# SUMMARY
# =============================================================================
from collections import Counter
tier_counts = Counter(n["tier"] for n in nodes)
risk_nodes  = [n["id"] for n in nodes if n["risk_node"]]

print("=== NexaCore Infrastructure Topology Generated ===")
print(f"Nodes: {len(nodes)}")
for tier, count in sorted(tier_counts.items()):
    print(f"  {tier:<30} {count}")
print(f"Edges: {len(edges)}")
print(f"Risk nodes: {risk_nodes}")

# Degree stats
out_deg = Counter(e[0] for e in edges)
in_deg  = Counter(e[1] for e in edges)
print(f"\nTop 10 by out-degree (most dependencies on others):")
for node_id, deg in out_deg.most_common(10):
    name = next(n["name"] for n in nodes if n["id"]==node_id)
    print(f"  {node_id:<22} {deg:>3}  {name}")
print(f"\nTop 10 by in-degree (most others depend on them):")
for node_id, deg in in_deg.most_common(10):
    name = next(n["name"] for n in nodes if n["id"]==node_id)
    print(f"  {node_id:<22} {deg:>3}  {name}")
