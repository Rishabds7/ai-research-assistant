/**
 * API SERVICE LAYER
 * Project: Research Assistant
 * File: frontend/src/lib/api.ts
 * 
 * This file defines all communication with the Django Backend.
 * It uses Axios for HTTP requests and defines the Type interfaces 
 * for consistent data handling across the frontend.
 */
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export const api = axios.create({
    baseURL: API_URL,
});

export const getMediaUrl = (path: string) => {
    if (!path) return '';
    if (path.startsWith('http')) return path;
    const baseUrl = API_URL.replace('/api', '');
    return `${baseUrl}${path}`;
};

// Helper to get or create a persistent session ID
const getSessionId = () => {
    if (typeof window === 'undefined') return '';
    let sessionId = localStorage.getItem('research_session_id');
    if (!sessionId) {
        sessionId = crypto.randomUUID();
        localStorage.setItem('research_session_id', sessionId);
    }
    return sessionId;
};

// Add interceptor to inject Session ID into every request
api.interceptors.request.use((config) => {
    const sessionId = getSessionId();
    if (sessionId) {
        config.headers['X-Session-ID'] = sessionId;
    }
    return config;
});

export interface Paper {
    id: string;
    filename: string;
    file: string; // URL to the PDF
    uploaded_at: string;
    processed: boolean;
    methodology_status: boolean;
    full_text?: string;
    methodology?: Methodology;
    section_summaries?: SectionSummary[];
    metadata?: {
        datasets?: string[];
        licenses?: string[];
    };
    task_ids?: {
        process_pdf?: string;
        summarize?: string;
        datasets?: string;
        licenses?: string;
    };
    uploadTaskId?: string;
    title?: string;
    authors?: string;
    year?: string;
    journal?: string;
    notes?: string;
    global_summary?: string;
}

export interface Methodology {
    id: string;
    datasets: string[] | any[];
    model: any;
    metrics: string[] | any[];
    results: any;
    summary: string;
}

export interface SectionSummary {
    id: string;
    section_name: string;
    summary: string;
    order_index?: number;
}

export const uploadPaper = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/papers/', formData);
    return response.data;
};

export const getPapers = async () => {
    const response = await api.get('/papers/');
    // Handle Django REST Framework pagination
    if (response.data && response.data.results) {
        return response.data.results;
    }
    return response.data;
};

export const getPaper = async (id: string) => {
    const response = await api.get(`/papers/${id}/`);
    return response.data;
};

export const extractMethodology = async (id: string) => {
    const response = await api.post(`/papers/${id}/extract_methodology/`);
    return response.data; // { task_id: ... }
};

export const extractAllSections = async (id: string) => {
    const response = await api.post(`/papers/${id}/extract_all_sections/`);
    return response.data; // { task_id: ... }
};

export const getTaskStatus = async (taskId: string) => {
    const response = await api.get(`/tasks/${taskId}/`);
    return response.data;
};

export const analyzeGaps = async (paperIds: string[]) => {
    const response = await api.post('/analysis/gaps/', { paper_ids: paperIds });
    return response.data; // { task_id: ... }
};

export const generateComparison = async (paperIds: string[]) => {
    const response = await api.post('/analysis/comparison/', { paper_ids: paperIds });
    return response.data; // { markdown: ... } (sync) or task_id
};

export const deletePaper = async (id: string) => {
    await api.delete(`/papers/${id}/`);
};

export const deleteAllPapers = async () => {
    await api.post('/papers/delete_all/');
};

export const updatePaper = async (id: string, data: Partial<Paper>) => {
    const response = await api.patch(`/papers/${id}/`, data);
    return response.data;
};

export const extractMetadata = async (id: string, field: 'datasets' | 'licenses') => {
    const response = await api.post(`/papers/${id}/extract_metadata/`, { field });
    return response.data; // { task_id: ... }
};

export const ingestArxiv = async (url: string) => {
    const response = await api.post('/papers/ingest_arxiv/', { url });
    return response.data; // { paper: ..., task_id: ... }
};

export const getBibTeX = async (id: string) => {
    const response = await api.get(`/papers/${id}/export_bibtex/`);
    return response.data; // { bibtex: ... }
};

// ===== COLLECTIONS API =====

export interface Collection {
    id: string;
    name: string;
    description: string;
    paper_count?: number;
    papers?: Paper[];
    created_at: string;
    updated_at: string;
}

export const getCollections = async (): Promise<Collection[]> => {
    const response = await api.get('/collections/');
    if (response.data && response.data.results) {
        return response.data.results;
    }
    return response.data;
};

export const getCollection = async (id: string): Promise<Collection> => {
    const response = await api.get(`/collections/${id}/`);
    return response.data;
};

export const createCollection = async (data: { name: string; description?: string }): Promise<Collection> => {
    const response = await api.post('/collections/', data);
    return response.data;
};

export const updateCollection = async (id: string, data: Partial<Collection>): Promise<Collection> => {
    const response = await api.patch(`/collections/${id}/`, data);
    return response.data;
};

export const deleteCollection = async (id: string): Promise<void> => {
    await api.delete(`/collections/${id}/`);
};

export const addPaperToCollection = async (collectionId: string, paperId: string) => {
    const response = await api.post(`/collections/${collectionId}/add_paper/`, { paper_id: paperId });
    return response.data;
};

export const removePaperFromCollection = async (collectionId: string, paperId: string) => {
    const response = await api.post(`/collections/${collectionId}/remove_paper/`, { paper_id: paperId });
    return response.data;
};
