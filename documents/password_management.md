# Password Management

## Overview
Guidelines for creating, resetting, and managing passwords.

## Policies
- Minimum length: 12 characters.
- Complexity: upper, lower, numbers, special characters.
- Rotation: every 90 days.
- Never reuse passwords across systems.

## Reset Procedure
1. Verify user identity via LDAP.
2. Generate temporary password.
3. Force password change on next login.
4. Log the reset in the audit trail.

## Category
Password Management

## Metadata
- Document ID: pwd-001
- Title: Password Management Guide
- Category: password
- Author: IT Security
- Version: 1.0
