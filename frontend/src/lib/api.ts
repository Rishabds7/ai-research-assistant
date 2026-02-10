/**
 * API SERVICE LAYER
 * Project: Research Assistant
 * File: frontend/src/lib/api.ts
 * 
 * This file defines all communication with the Django Backend.
 * It uses Axios for HTTP requests and defines the Type interfaces 
 * for consistent data handling across the frontend.
 */
import axios, { AxiosResponse } from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export const api = axios.create({
    baseURL: API_URL,
});

/**
 * Returns the full URL for a media file.
 * @param path Relative path from the API response
 */
export const getMediaUrl = (path: string): string => {
    if (!path) return '';
    if (path.startsWith('http')) return path;

    const baseUrl = API_URL.replace(/\/api\/?$/, '');
    // Ensure path starts with a slash
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${baseUrl}${normalizedPath}`;
};

// Helper to get or create a persistent session ID
const getSessionId = (): string => {
    if (typeof window === 'undefined') return '';
    let sessionId = localStorage.getItem('research_session_id');
    if (!sessionId) {
        sessionId = crypto.randomUUID();
        localStorage.setItem('research_session_id', sessionId);
        console.log('[Session] Created new session ID:', sessionId);
    } else {
        console.log('[Session] Retrieved existing session ID:', sessionId);
    }
    return sessionId;
};

// Add interceptor to inject Session ID into every request
api.interceptors.request.use((config) => {
    const sessionId = getSessionId();
    if (sessionId) {
        config.headers['X-Session-ID'] = sessionId;
        console.log('[API] Request to:', config.url, 'with Session ID:', sessionId);
    } else {
        console.warn('[API] No session ID available for request to:', config.url);
    }
    return config;
});

// --- TYPE DEFINITIONS ---

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
        swot_analysis?: string;
    };
    uploadTaskId?: string;
    title?: string;
    authors?: string;
    year?: string;
    journal?: string;
    notes?: string;
    global_summary?: string;
    swot_analysis?: string;
    swot_analysis_updated_at?: string;
}

export interface Methodology {
    id: string;
    datasets: string[];
    model: Record<string, any>; // Flexible JSON object
    metrics: string[];
    results: Record<string, any>; // Flexible JSON object
    summary: string;
}

export interface SectionSummary {
    id: string;
    section_name: string;
    summary: string;
    order_index?: number;
}

export interface TaskByIdResponse {
    task_id: string;
}

export interface TaskStatusResponse {
    task_id: string;
    task_type: string; // 'process_pdf', 'summarize', etc.
    status: 'pending' | 'running' | 'completed' | 'failed' | 'timeout';
    result?: any;
    error?: string;
    created_at: string;
    updated_at: string;
}

export interface AnalysisResponse {
    markdown: string;
}

// --- API CLIENT FUNCTIONS ---

/**
 * Uploads a PDF paper to the backend.
 * @param file The PDF file object
 */
export const uploadPaper = async (file: File): Promise<{ paper: Paper; task_id: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<{ paper: Paper; task_id: string }>('/papers/', formData);
    return response.data;
};

/**
 * Fetches all papers.
 */
export const getPapers = async (): Promise<Paper[]> => {
    const response = await api.get<any>('/papers/', {
        headers: {
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    });
    console.log('[API] getPapers response:', response.data);
    // Handle Django REST Framework pagination
    if (response.data && response.data.results) {
        console.log('[API] Found', response.data.results.length, 'papers (paginated)');
        return response.data.results;
    }
    console.log('[API] Found', (response.data as Paper[]).length, 'papers (direct array)');
    return response.data as Paper[];
};

/**
 * Fetches a single paper by ID.
 * @param id Paper ID
 */
export const getPaper = async (id: string): Promise<Paper> => {
    const response = await api.get<Paper>(`/papers/${id}/`);
    return response.data;
};

/**
 * Triggers methodology extraction.
 */
export const extractMethodology = async (id: string): Promise<TaskByIdResponse> => {
    const response = await api.post<TaskByIdResponse>(`/papers/${id}/extract_methodology/`);
    return response.data;
};

/**
 * Triggers extraction of all sections (Abstract, Intro, etc.).
 */
export const extractAllSections = async (id: string): Promise<TaskByIdResponse> => {
    const response = await api.post<TaskByIdResponse>(`/papers/${id}/extract_all_sections/`);
    return response.data;
};

/**
 * Checks the status of a background task.
 * @param taskId The Celery task ID
 */
export const getTaskStatus = async (taskId: string): Promise<TaskStatusResponse> => {
    const response = await api.get<TaskStatusResponse>(`/tasks/${taskId}/`);
    return response.data;
};

/**
 * Analyzes research gaps across multiple papers.
 */
export const analyzeGaps = async (paperIds: string[]): Promise<TaskByIdResponse> => {
    const response = await api.post<TaskByIdResponse>('/analysis/gaps/', { paper_ids: paperIds });
    return response.data;
};

/**
 * Generates a comparison matrix/text for papers.
 */
export const generateComparison = async (paperIds: string[]): Promise<AnalysisResponse | TaskByIdResponse> => {
    const response = await api.post<AnalysisResponse | TaskByIdResponse>('/analysis/comparison/', { paper_ids: paperIds });
    return response.data;
};

/**
 * Deletes a single paper.
 */
export const deletePaper = async (id: string): Promise<void> => {
    await api.delete(`/papers/${id}/`);
};

/**
 * Deletes ALL papers. 
 * WARNING: Destructive action.
 */
export const deleteAllPapers = async (): Promise<void> => {
    await api.post('/papers/delete_all/');
};

/**
 * Deletes ALL collections. 
 * WARNING: Destructive action.
 */
export const deleteAllCollections = async (): Promise<void> => {
    await api.post('/collections/delete_all/');
};

/**
 * Triggers gap analysis for a collection.
 * @param collectionId Collection ID
 */
export const analyzeCollectionGaps = async (collectionId: string): Promise<TaskByIdResponse> => {
    const response = await api.post<TaskByIdResponse>(`/collections/${collectionId}/analyze_gaps/`);
    return response.data;
};

export const analyzeSwot = async (id: string): Promise<TaskByIdResponse> => {
    const response = await api.post<TaskByIdResponse>(`/papers/${id}/analyze_swot/`);
    return response.data;
};

/**
 * Updates paper metadata (notes, title, etc.).
 */
export const updatePaper = async (id: string, data: Partial<Paper>): Promise<Paper> => {
    const response = await api.patch<Paper>(`/papers/${id}/`, data);
    return response.data;
};

/**
 * Triggers specific metadata extraction (datasets or licenses).
 */
export const extractMetadata = async (id: string, field: 'datasets' | 'licenses'): Promise<TaskByIdResponse> => {
    const response = await api.post<TaskByIdResponse>(`/papers/${id}/extract_metadata/`, { field });
    return response.data;
};

/**
 * Ingests a paper directly from an arXiv URL.
 */
export const ingestArxiv = async (url: string): Promise<{ paper: Paper; task_id: string }> => {
    const response = await api.post<{ paper: Paper; task_id: string }>('/papers/ingest_arxiv/', { url });
    return response.data;
};

/**
 * Exports the paper's citation in BibTeX format.
 */
export const getBibTeX = async (id: string): Promise<{ bibtex: string }> => {
    const response = await api.get<{ bibtex: string }>(`/papers/${id}/export_bibtex/`);
    return response.data;
};

// ===== COLLECTIONS API =====

export interface Collection {
    id: string;
    name: string;
    description: string;
    paper_count?: number;
    paper_ids?: string[];  // For duplicate detection
    papers?: Paper[];      // Only in detail view
    gap_analysis?: string;
    gap_analysis_updated_at?: string;
    created_at: string;
    updated_at: string;
}

/**
 * Fetches all collections.
 */
export const getCollections = async (): Promise<Collection[]> => {
    const response = await api.get<any>('/collections/');
    if (response.data && response.data.results) {
        return response.data.results;
    }
    return response.data as Collection[];
};

/**
 * Fetches a single collection by ID.
 */
export const getCollection = async (id: string): Promise<Collection> => {
    const response = await api.get<Collection>(`/collections/${id}/`);
    return response.data;
};

/**
 * Creates a new collection.
 */
export const createCollection = async (data: { name: string; description?: string }): Promise<Collection> => {
    const response = await api.post<Collection>('/collections/', data);
    return response.data;
};

/**
 * Updates an existing collection.
 */
export const updateCollection = async (id: string, data: Partial<Collection>): Promise<Collection> => {
    const response = await api.patch<Collection>(`/collections/${id}/`, data);
    return response.data;
};

/**
 * Deletes a collection.
 */
export const deleteCollection = async (id: string): Promise<void> => {
    await api.delete(`/collections/${id}/`);
};

/**
 * Adds a paper to a collection.
 */
export const addPaperToCollection = async (collectionId: string, paperId: string): Promise<any> => {
    const response = await api.post(`/collections/${collectionId}/add_paper/`, { paper_id: paperId });
    return response.data;
};

/**
 * Removes a paper from a collection.
 */
export const removePaperFromCollection = async (collectionId: string, paperId: string): Promise<any> => {
    const response = await api.post(`/collections/${collectionId}/remove_paper/`, { paper_id: paperId });
    return response.data;
};
