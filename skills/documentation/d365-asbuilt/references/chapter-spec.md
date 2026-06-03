# Chapter Specification

## Step 0: Master Instruction

Set persona as senior Microsoft Power Platform Technical Architect and Technical Writer. Generate a professional Dynamics 365 Contact Centre as-built document. Maintain consistency, never abbreviate names, use full display names, and only document custom components (`ec_`, `ecsm_`) or customized standard components. For missing information state exactly: `Information not available in provided solution metadata`.

Generate only the section explicitly requested and wait for follow-up instructions.

## Chapter 1: Executive Summary

Include:
- Application purpose
- Business value
- Target users
- Environment details
- Document scope
- Intended audience

## Chapter 2: Application Architecture Overview

Include:
- Architecture narrative
- Dataverse tables
- Power Automate flows
- JavaScript web resources
- Environment variables
- Security layer

Required table columns:
- Component
- Type
- Purpose

## Chapter 3: Dataverse Table Inventory

Per table include:
- Full Display Name
- Schema Name
- Table Type
- Primary Column
- Business Purpose

Attribute table columns:
- Display Name
- Schema Name
- Data Type
- Required
- Description

Relationships table columns:
- Relationship Name
- Type
- Related Table
- Lookup Column
- Purpose

If none, output: `No relationships defined.`

## Chapter 4A: Flow Analysis

For each flow include:
- Full name
- Trigger
- Tables used
- Step-by-step logic
- Conditions with exact values

Do not group flows and do not generate diagrams in this step.

## Chapter 4B: Flow Grouping

Group flows only when trigger, structure, and action sequence are the same.

Output columns:
- Group #
- Pattern
- Representative Flow
- # Flows
- Trigger Table
- Trigger Type

## Chapter 5: JavaScript Web Resources

Include:
- File name
- Schema
- Forms/tables
- Event handlers
- Function logic
- Dependencies

## Chapter 6: Environment Variables

Columns:
- Display Name
- Schema Name
- Type
- Value
- Purpose
- Used By

## Chapter 7: Security Roles

Include:
- Role name
- Purpose
- Privileges table

## Chapter 8: Plugin Assemblies and Server-Side Extensions

Only include provided custom assemblies and related components:
- Plugin Assemblies
- Plugin Types
- Plugin Steps
- Plugin Images

## Chapter 9: Custom APIs and Custom Process Actions

Only include explicitly provided metadata:
- Custom APIs
- Request parameters
- Response properties
- Bound/unbound configuration
- Plugin handlers

## Chapter 10: Integration Architecture

Synthesize only from:
- Flows
- Environment variables
- Custom APIs
- Plugin assemblies

Cross-reference components and avoid repetition of previous chapters.

## Chapter 11: Customized Standard Tables

Only include standard tables confirmed as customized in solution metadata.
Exclude:
- Fully custom tables
- Standard tables with no explicit customization evidence
