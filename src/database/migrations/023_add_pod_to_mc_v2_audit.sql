-- Migration 023: Add pod column to mc_v2_audit_by_customer
ALTER TABLE mc_v2_audit_by_customer ADD COLUMN IF NOT EXISTS pod VARCHAR(100);
