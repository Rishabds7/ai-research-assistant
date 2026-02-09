/**
 * UTILITY FUNCTIONS
 * Project: Research Assistant
 * File: frontend/src/lib/utils.ts
 * 
 * Common helper functions for class merging (Tailwind) and safe data parsing.
 */
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}

export function safeString(value: any, fallback: string = ""): string {
    if (value === null || value === undefined) return fallback;
    if (typeof value === 'string') return value;
    if (typeof value === 'number') return String(value);
    if (typeof value === 'boolean') return String(value);
    if (typeof value === 'object') {
        // Try common properties if it's an object (e.g. from a bad LLM return)
        return value.name || value.title || value.label || JSON.stringify(value);
    }
    return String(value);
}

export function safeArray(value: any): any[] {
    if (Array.isArray(value)) return value;
    return [];
}
