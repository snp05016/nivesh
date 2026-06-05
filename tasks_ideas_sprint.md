# Ideas Workspace Sprint

## PHASE 0: Setup
- [x] Create implementation ledger
- [ ] Clone external repos (/tmp/nivesh_clones/)
- [ ] Study scraping patterns from cloned repos

## PHASE 1: Backend Database + API
- [ ] Add AdvisorBiography table to database.py
- [ ] Add TextAdvisoryInsight table to database.py
- [ ] Add IdeasErrorLog table to database.py
- [ ] GET /api/v1/ideas/advisors endpoint
- [ ] GET /api/v1/ideas/feed endpoint
- [ ] GET /api/v1/admin/ideas-errors endpoint
- [ ] Populate AdvisorBiography with SEBI-registered advisors

## PHASE 2: iOS Models + Views
- [ ] Add Codable structs to Models.swift
- [ ] Add NetworkManager functions
- [ ] Build AdvisorBioCard.swift
- [ ] Refactor Ideas view with 2-segment layout (Advisory Wire + Verified Minds)

## PHASE 3: Integration Testing
- [ ] Verify backend syntax + routes
- [ ] curl-test new endpoints

## PHASE 4: State Retention
- [ ] Git add + commit
