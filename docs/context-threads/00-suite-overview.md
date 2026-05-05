# Thread: Suite Overview

## Objective

Ascend HSI needs a unified EB1A operations platform to replace fragmented work currently spread across Google Drive, Gmail, local downloads, offline drafting, and manual coordination.

## Product Vision

The product is not only a member upload portal. It is a role-based operating system for:

- member intake
- profile building
- leader oversight
- attorney review and petition strategy
- operations monitoring

## Active Role Experiences

### Member

- maintain profile
- upload and organize evidence
- plan future evidence-building activity
- receive and reply to messages

### Profile Builder

- monitor assigned members
- push opportunities
- assign tasks
- identify gaps and next actions

### Leader

- invite members
- assign builders
- assign attorneys
- review domain mix, risk, capacity, and member routing
- manage assignment oversight
- assume builder and attorney views without leaving leader auth

### Attorney

- review full portfolio caseboard
- review full dossier
- assess strengths and gaps
- handle batch intake
- review evidence separately
- generate AI petition draft

### Admin / Operations

- track OpenAI usage
- track active members
- track operational errors
- inspect portal and connection health
- manage support tickets
- debug member issues

## Navigation Pattern

The suite has moved away from one giant page and now uses child pages per role. Messaging is a dedicated page across all portals.

## Shared System Capabilities

- portal selector login
- role-aware side navigation
- dedicated child pages per portal
- member profile tabs
- evidence intake with AI + manual routes
- event planner
- evidence-by-criterion views
- folder organization
- threaded messaging
- leader perspective switching
- assignment oversight
- opportunity library and task assignment
- attorney batch intake
- attorney petition generator
- admin operational dashboard and support queue

## Current Platform

- frontend: React
- backend: FastAPI
- database: SQLite
- file storage: Google Drive
- AI: OpenAI API with fallback behavior

## Core Product Principle

Each portal should feel purpose-built for its role, while still operating on the same shared case record.
