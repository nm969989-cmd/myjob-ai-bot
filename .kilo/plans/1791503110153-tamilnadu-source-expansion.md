# Comprehensive Tamil Nadu Job Source Expansion Plan

## Goal
Expand the `tn-live-jobs` scraper to cover **all major Tamil Nadu job sources** — government portals, enterprise ATS, job boards, startup platforms — so no Tamil Nadu vacancy is missed.

## Current Coverage (verified)

### Tier 1 — Government (always runs)
- `tn.gov.in` (job_opportunity_list.php AJAX)
- `tnpsc.gov.in` (TNPSC notifications)
- `tnvelaivaaippu.gov.in` (Employment & Training)
- `employment.tn.gov.in` (Employment Exchange) — often blocked
- `protnnetc.tn.gov.in` (Private Employment Exchange) — often blocked
- `mrb.tn.gov.in` (Medical Services Recruitment Board)
- 4 District NIC sites: `madurai.nic.in`, `salem.nic.in`, `tirunelveli.nic.in`, `coimbatore.nic.in`

### Tier 1 — Company Careers (always runs)
- Zoho (public JSON API)
- Freshersworld (HTML listings per keyword+city)
- SPA companies via Playwright: TCS, Infosys, Wipro, HCLTech, Cognizant (often blocked)

### Tier 1 — Enterprise ATS APIs (always runs)
- **SmartRecruiters**: Freshworks, Robert Bosch India, Avery Dennison
- **Workday CXS**: Kyndryl, AstraZeneca, PayPal

### Tier 2 — Job Portals (run, often blocked)
- Naukri (Playwright, often blocked)
- apna.co (flight JSON payload)
- Indeed India (blocked by Cloudflare 403)
- LinkedIn (guest search endpoint, rate-limited)
- Internshala (Tier 3, optional, only with `ENABLE_TIER3=true`)

## Missing Major Sources — Categorized

### A. Missing Government Portals (Tier 1 — HIGH PRIORITY)
| Portal | URL | Notes |
|--------|-----|-------|
| Tamil Nadu Teachers Recruitment Board | `trb.tn.gov.in` | Teacher/lecturer posts |
| Tamil Nadu Uniformed Services Recruitment Board | `tnusrb.tn.gov.in` | Police, fire, prison constables |
| Tamil Nadu Revenue Department | `revenue.tn.gov.in` | VAO, revenue inspector |
| Tamil Nadu Public Works Department | `pwd.tn.gov.in` | Engineering/technical posts |
| TANGEDCO (TN Generation & Distribution Corp) | `tangedco.gov.in` | Power sector jobs |
| TWAD Board (Water Supply & Drainage) | `twadboard.tn.gov.in` | Water/engineering |
| Chennai Metro Rail Limited | `chennaimetrorail.org` | Metro/engineering |
| TNUSRB | `tnusrb.tn.gov.in` | Already listed |
| Tamil Nadu Police | `tnpolice.gov.in` | Constables, SI, etc. |
| Tamil Nadu Fire & Rescue Services | `tnfrs.tn.gov.in` | Fireman posts |
| Tamil Nadu Prison Department | `prisons.tn.gov.in` | Warder, etc. |
| Tamil Nadu Forest Department | `forests.tn.gov.in` | Forest guard, ranger |
| Tamil Nadu Fisheries Department | `fisheries.tn.gov.in` | Fisheries posts |
| Tamil Nadu Agriculture Department | `agri.tn.gov.in` | Agriculture officer |
| Tamil Nadu Horticulture | `horticulture.tn.gov.in` | Horticulture posts |
| Tamil Nadu Animal Husbandry | `animalhusbandry.tn.gov.in` | Veterinary posts |
| Tamil Nadu Dairy Development | `aavinmilk.com` | Dairy/cooperative jobs |
| Tamil Nadu Cooperative Dept | `cooperation.tn.gov.in` | Cooperative bank jobs |
| Tamil Nadu Small Industries (TANSIDCO) | `tansidco.tn.gov.in` | MSME jobs |
| TNIIC (TN Industrial Investment Corp) | `tniic.tn.gov.in` | Industrial finance |
| SIPCOT | `sipcot.tn.gov.in` | Industrial parks jobs |
| TIDCO (TN Industrial Development Corp) | `tidco.tn.gov.in` | Infrastructure jobs |
| Chennai Corporation / GCC | `chennaicorporation.gov.in` | Municipal jobs |
| Coimbatore Corporation | `ccmc.gov.in` | Municipal jobs |
| Madurai Corporation | `maduraicorporation.gov.in` | Municipal jobs |
| Trichy Corporation | `trichycorporation.gov.in` | Municipal jobs |
| Salem Corporation | `salemcorporation.gov.in` | Municipal jobs |
| Tirunelveli Corporation | `tirunelvelicorporation.gov.in` | Municipal jobs |
| Tiruppur Corporation | `tiruppurcorporation.gov.in` | Municipal jobs |
| Erode Corporation | `erodecorporation.gov.in` | Municipal jobs |
| Thanjavur Corporation | `thanjavurcorporation.gov.in` | Municipal jobs |
| **Missing 34+ District Collectorates** | `*.nic.in/notice_category/recruitment/` | Only 4 of 38 districts covered |

### B. Missing Enterprise ATS Platforms (Tier 1 — HIGH PRIORITY)
| Platform | Example Companies | Integration Type |
|----------|-------------------|------------------|
| **Workday CXS** | Amazon, Google, Microsoft, Meta, Flipkart, PhonePe, Swiggy, Zomato, Ola, Byju's, Razorpay, CRED, Meesho, Unacademy, Postman, Chargebee, BrowserStack, Turing, Rippling, GitLab, HashiCorp, Databricks, Snowflake, MongoDB, Confluent, CockroachDB, PlanetScale, Neon, Turso, Upstash, Railway, Render, Fly.io, SingleStore, Timescale, CockroachDB, Yugabyte | Public JSON API (CXS) |
| **Greenhouse.io** | GitLab, HashiCorp, Databricks, Snowflake, MongoDB, Confluent, CockroachDB, PlanetScale, Neon, Turso, Upstash, Railway, Render, Fly.io, SingleStore, Timescale, Yugabyte | Public JSON API |
| **Lever.co** | Many startups, mid-market | Public JSON API |
| **JazzHR** | SMB/mid-market | API or HTML |
| **BambooHR** | SMB | API |
| **iCIMS** | Large enterprises | HTML/JSON |
| **Jobvite** | Mid-large | HTML/JSON |
| **BrassRing (Kenexa)** | Large corps (IBM, etc.) | HTML |
| **Oracle Taleo** | Very large corps | HTML |
| **SAP SuccessFactors** | Fortune 500 | OData/API |
| **PeopleSoft** | Enterprise | HTML |
| **UKG (Ultimate Kronos)** | Enterprise | HTML |
| **Eightfold.ai** | AI-powered ATS | API |
| **Phenom People** | AI ATS | API |
| **SmartRecruiters** (expand) | More companies | Already have 3, add more |

### C. Missing Indian Job Portals (Tier 2 — HIGH PRIORITY)
| Portal | URL | Approach |
|--------|-----|----------|
| **TimesJobs** | `timesjobs.com` | Playwright + HTML parse |
| **Monster India** | `monsterindia.com` | Playwright + HTML/JSON |
| **Shine.com** | `shine.com` | Playwright + HTML/JSON |
| **Glassdoor India** | `glassdoor.co.in` | Playwright (may need login) |
| **CutShort.io** | `cutshort.io` | Public API or Playwright |
| **Wellfound (AngelList Talent)** | `wellfound.com` | Playwright + GraphQL |
| **Hirect** | `hirect.in` | Playwright + API |
| **PlacementIndia** | `placementindia.com` | HTML parse |
| **JobHai** | `jobhai.com` | Playwright (blue-collar focus) |
| **QuikrJobs** | `quikrjobs.com` | Playwright + HTML |
| **NCS (National Career Service)** | `ncs.gov.in` | Government, HTML |
| **Fresherslive** | `fresherslive.com` | HTML parse |
| **FreshersNow** | `freshersnow.com` | HTML parse |
| **AllIndiaJobs** | `allindiajobs.in` | HTML parse |
| **Sarkari Naukri** | `sarkarinaukri.in` | Govt job aggregator |
| **FreeJobAlert** | `freejobalert.com` | Govt/PSU job alerts |
| **Sarkari Result** | `sarkariresult.com` | Govt exam results + jobs |
| **Employment News** | `employmentnews.gov.in` | Weekly govt jobs |
| **Rozgar.com** | `rozgar.com` | HTML parse |

### D. Missing Startup/Tech Platforms (Tier 2/3 — MEDIUM PRIORITY)
| Platform | URL | Approach |
|----------|-----|----------|
| **CutShort** | `cutshort.io` | Public API or GraphQL |
| **Wellfound** | `wellfound.com` | Playwright + GraphQL |
| **Hirect** | `hirect.in` | Playwright |
| **Internshala** | Already Tier 3 | Enable by default? |
| **LinkedIn** | Already Tier 2 | Improve reliability |
| **AngelList/Wellfound** | Already listed | |
| **Y Combinator Jobs** | `ycombinator.com/jobs` | Playwright |
| **HackerNews Who's Hiring** | Monthly thread | API/HTML |
| **Stack Overflow Jobs** | Discontinued | — |
| **GitHub Jobs** | Discontinued | — |

### E. Missing Major Company ATS (Tier 1 — HIGH PRIORITY)
Add to `tech-ats.js` Workday/Greenhouse/Lever lists:

| Company | ATS | Notes |
|---------|-----|-------|
| Amazon | Workday | Multiple regions |
| Google | Workday | Multiple regions |
| Microsoft | Workday | Multiple regions |
| Meta/Facebook | Workday | Multiple regions |
| Flipkart | Workday | India focus |
| PhonePe | Workday | India focus |
| Swiggy | Workday | India focus |
| Zomato | Workday | India focus |
| Ola | Workday | India focus |
| Byju's | Workday | India focus |
| Razorpay | Workday | India focus |
| CRED | Workday | India focus |
| Meesho | Workday | India focus |
| Unacademy | Workday | India focus |
| Postman | Workday | India focus |
| Chargebee | Workday | India focus |
| BrowserStack | Workday | India focus |
| Turing | Workday | Global/remote |
| Rippling | Workday | Global |
| GitLab | Greenhouse | Global |
| HashiCorp | Greenhouse | Global |
| Databricks | Greenhouse | Global |
| Snowflake | Workday | Global |
| MongoDB | Greenhouse | Global |
| Confluent | Greenhouse | Global |
| CockroachDB | Greenhouse | Global |
| PlanetScale | Greenhouse | Global |
| Neon | Greenhouse | Global |
| Turso | Greenhouse | Global |
| Upstash | Greenhouse | Global |
| Railway | Greenhouse | Global |
| Render | Greenhouse | Global |
| Fly.io | Greenhouse | Global |
| SingleStore | Greenhouse | Global |
| Timescale | Greenhouse | Global |
| Yugabyte | Greenhouse | Global |
| Turing.com | Workday | Global |
| Postman | Workday | India focus |
| Chargebee | Workday | India focus |
| BrowserStack | Workday | India focus |

## Implementation Strategy

### Phase 1 — Government Portals (Week 1-2)
1. Create `govt-tn-extended.js` module with all missing government portals
2. Add 34+ district collectorate NIC sites to config
3. Add TRB, TNUSRB, TANGEDCO, TWAD, Revenue, PWD, Police, Fire, Forest, Fisheries, Agriculture, etc.
4. Test each for accessibility (many are internal/blocked)

### Phase 2 — Enterprise ATS Expansion (Week 2-3)
1. Add **Greenhouse.io** source module (public job board API)
2. Add **Lever.co** source module
3. Expand `tech-ats.js` Workday list with 50+ major tech companies
4. Add Greenhouse.io source for companies using it
5. Add Lever.co source module

### Phase 3 — Indian Job Portals (Week 3-4)
1. Create `timesjobs.js` source (Playwright)
2. Create `monsterindia.js` source
3. Create `shine.js` source
4. Create `cutshort.js` source (check for public API)
5. Create `wellfound.js` source (Playwright + GraphQL)
6. Create `hirect.js` source
7. Create `jobhai.js` source
8. Create `quikrjobs.js` source
9. Create `ncs.js` (National Career Service - govt)

### Phase 4 — District Coverage Completion (Week 1)
1. Add all 38 Tamil Nadu districts to `config.js` CITIES and CITY_ALIASES
2. Update `govt-tn.js` DISTRICT_SITES to include all 38 district NIC sites
3. Add city aliases for all districts

### Phase 5 — Config & Integration (Ongoing)
1. Update `config.js` CITIES with all 38 districts
2. Update `config.js` CITY_ALIASES with all spelling variants
3. Update `config.js` SEARCH_KEYWORDS if needed
4. Add new sources to `tn-live-jobs/src/sources/index.js` with appropriate tiers
5. Update `SITE_TIERS` in `index.js`

## Configuration Updates Required

### `tn-live-jobs/src/config.js` — Add all 38 districts
```javascript
const CITIES = [
  'Tiruvannamalai', 'Vellore', 'Puducherry', 'Chennai',  // Priority
  'Coimbatore', 'Madurai', 'Trichy', 'Salem', 'Tirunelveli', 'Erode', 'Thanjavur', 'Tiruppur',
  'Kanchipuram', 'Villupuram', 'Cuddalore', 'Dindigul', 'Karur', 'Namakkal', 'Perambalur',
  'Ariyalur', 'Nagapattinam', 'Thiruvarur', 'Mayiladuthurai', 'Tenkasi', 'Chengalpattu',
  'Kallakurichi', 'Ranipet', 'Tirupattur', 'Tiruvallur', 'Ramanathapuram', 'Sivaganga',
  'Virudhunagar', 'Thoothukudi', 'Kanyakumari', 'Nilgiris', 'Dharmapuri', 'Krishnagiri',
  'Tamil Nadu'
];
```

### `tn-live-jobs/src/config.js` — CITY_ALIASES for all districts
Add aliases for each district (English + Tamil spellings, common abbreviations).

### `tn-live-jobs/src/sources/index.js` — Register new sources
```javascript
const govtTnExtended = require('./govt-tn-extended');
const timesjobs = require('./timesjobs');
const monsterindia = require('./monsterindia');
const shine = require('./shine');
const cutshort = require('./cutshort');
const wellfound = require('./wellfound');
const hirect = require('./hirect');
const jobhai = require('./jobhai');
const ncs = require('./ncs');
const greenhouse = require('./greenhouse');
const lever = require('./lever');

const ALL_SOURCES = [
  govtTn, govtTnExtended, companyCareers, techAts,
  naukri, apna, indeed, linkedin, internshala,
  timesjobs, monsterindia, shine, cutshort, wellfound, hirect, jobhai, ncs,
  greenhouse, lever
];
```

## Risk Mitigation
- **Rate limiting**: Each new source gets its own delay/timeout config
- **Blocking**: Graceful degradation — log and continue
- **Maintenance**: Each source in own file, easy to disable
- **Testing**: Run with `ENABLE_TIER3=true` for optional sources

## Validation
- Run scraper with `node tn-live-jobs/src/cli.js --test`
- Verify each new source returns jobs for Tamil Nadu
- Check `data/jobs.json` for new source entries
- Monitor run reports for blocked/unreachable sources

## Out of Scope
- Portals requiring login/authentication
- Portals with aggressive CAPTCHA that can't be bypassed ethically
- International job portals not focused on India
- Sources with no Tamil Nadu listings historically

---

**Priority Order for Implementation:**
1. **District collectorates** (34 missing) — config only, immediate impact
2. **Government portals** (TRB, TNUSRB, TANGEDCO, etc.) — high value, Tier 1
3. **Workday expansion** (50+ companies) — high value, Tier 1, JSON API
4. **Greenhouse.io** source — high value, many tech companies
5. **Lever.co** source — high value, many startups
6. **TimesJobs, Monster, Shine** — Tier 2, major Indian portals
7. **CutShort, Wellfound, Hirect** — Tier 2, startup-focused
8. **JobHai, QuikrJobs, NCS** — Tier 2, niche/blue-collar/govt