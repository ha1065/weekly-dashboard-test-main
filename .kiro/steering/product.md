# Product Overview

## What is iCivics LMS?

iCivics is an educational platform that provides civics education through games, interactive resources, and a Learning Management System (LMS). Phase 3+4 is a full-stack rebuild of the LMS platform and two marketing landing pages, built on AWS serverless infrastructure.

## Target Users

| Role    | Who                        | What they do                                                              |
| ------- | -------------------------- | ------------------------------------------------------------------------- |
| Teacher | Educators using iCivics    | Create classes, assign resources, view student results, manage students   |
| Student | K-12 students              | Join classes via class code, complete assignments, view achievements      |
| Visitor | Unauthenticated site users | Browse Play & Learn and Teach landing pages, sign up                     |

## Core Domains

- **User Service** — Profile management, avatar display/create, username re-roll, account cancellation
- **LMS Service** — Classes CRUD, assignments CRUD, student assignment progress, class membership
- **Achievements** — Game-to-achievement pipeline, earned achievements display
- **Favorites** — Add/remove resource favorites by resource GUID (node_id integer)
- **Activity Feed** — Chronological student activity log (separate Postgres instance)
- **Landing Pages** — Play & Learn + Teach pages with dynamic S3 JSON content, SEO, UTM/GA4 tracking
- **Kami Integration** — Document upload/retrieval for Kami lesson plans
- **State Portals** — Hardcoded JSON per state (4 states), linked by user's state field

## Authentication Model

- Auth is **owned by iCivics** — not built by Cloudelligent
- Three authenticator types: username/password, Google, Clever
- Cloudelligent reads auth tokens and enforces ownership checks (e.g., class owner = requesting teacher)
- Student registration via class code: create user, then link to class (Cloudelligent implements join logic)
- `default_student_password` used only for teacher-created students; self-registered students keep their own password

## Key Data Entities (from ERD)

- `User` (uid PK), `username_authenticator`, `google_authenticator`, `clever_authenticator`
- `avatar`, `avatar_parts`, `marketing_identifiers`
- `Classes` (class_id PK, class_code auto-generated UNIQUE, owner_uid FK)
- `Assignments` (assignment_id PK, class_id FK, resource_identifier varchar, title, description, due_date)
- `user_to_assignment` (junction — denormalized snapshot of assignment at enrollment time)
- `user_to_class` (junction), `user_to_role` (junction)
- `roles` (role_id PK, role_name, role_group — Educator group + Grade group)
- `favorites` (uid FK, resource_id), `achievements`, `kami_user_data`, `quiz_response`
- `mdr_building` (MDR school directory)
- Resource identifier = `node_id` (integer), stable across all environments

## Key Business Rules

- Assignments with `due_date` in the past must NOT be allowed at creation time
- Assignment deletion = soft-delete (no unarchive/undelete for teachers; data retained for analytics)
- Classes are archived, not deleted
- Class code is auto-generated and stored as a unique value
- Column name: use `resource_identifier` (fix ERD typo `resource_idenitfier`)
- Activity feed stored in separate Postgres instance (not main DB); Timestream out of scope
- Landing page content stored as S3 JSON (not RDS); manual dev upload short-term, CMS long-term
- Analytics platform: GA4; UTM params not persisted (pass-through only)
- State portals: hardcoded JSON files, 1 per state, 4 states supported; state field on linked user table

## Timeline

- **Code freeze: June 5, 2026**
- iCivics company retreat: June 8-10 (team unavailable)
- 30-45 day maintenance/validation window after all phases complete
