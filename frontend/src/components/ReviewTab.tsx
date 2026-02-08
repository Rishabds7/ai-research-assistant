"use client";

import { Paper, updatePaper, Collection, getCollections } from "@/lib/api";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { Button } from "./ui/button";
import { Download, FileEdit, X, ChevronDown, FolderOpen } from "lucide-react";
import React, { useState, useEffect } from "react";
import { Textarea } from "./ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

/**
 * AI REVIEW DASHBOARD
 * 
 * Purpose: This component acts as a high-level comparison matrix for research.
 * It aggregates 'Global Summaries' (TL;DRs) from multiple papers into a 
 * single structured view, enabling quick cross-paper synthesis.
 * 
 * AI Features:
 * 1. Summary Aggregation: Displays the result of the 'Global Summary' task.
 * 2. Export: Allows researchers to download the AI insights into a CSV for external analysis.
 */
interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    children: React.ReactNode;
    footer?: React.ReactNode;
}

function Modal({ isOpen, onClose, title, children, footer }: ModalProps) {
    if (!isOpen) return null;
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#1A365D]/40 backdrop-blur-md animate-in fade-in duration-300">
            <div className="bg-[#FDFBF7] rounded-3xl shadow-2xl w-full max-w-lg overflow-hidden border border-[#F1E9D2] animate-in zoom-in duration-300">
                <div className="flex items-center justify-between p-6 border-b border-[#F1E9D2]/50 bg-white">
                    <h3 className="text-xl font-extrabold text-[#1A365D] tracking-tight">{title}</h3>
                    <button onClick={onClose} className="p-2 rounded-xl hover:bg-[#FDFBF7] text-slate-400 hover:text-[#D4AF37] transition-all">
                        <X className="h-6 w-6" />
                    </button>
                </div>
                <div className="p-8">{children}</div>
                {footer && <div className="flex justify-end gap-4 p-6 bg-white border-t border-[#F1E9D2]/50">{footer}</div>}
            </div>
        </div>
    );
}

interface ReviewTabProps {
    papers: Paper[];
    onUpdate: () => void;
}

export function ReviewTab({ papers, onUpdate }: ReviewTabProps) {
    const [expandedPapers, setExpandedPapers] = useState<Set<string>>(new Set());
    const [editingPaper, setEditingPaper] = useState<Paper | null>(null);
    const [notes, setNotes] = useState("");
    const [collections, setCollections] = useState<Collection[]>([]);
    const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(null);

    // Fetch collections on mount
    useEffect(() => {
        const fetchCollections = async () => {
            try {
                const data = await getCollections();
                setCollections(data);
            } catch (error) {
                console.error('Failed to fetch collections:', error);
            }
        };
        fetchCollections();
    }, []);

    // Filter papers by selected collection
    let reviewedPapers = papers.filter(
        (p) => (p.section_summaries && p.section_summaries.length > 0) || p.global_summary
    );

    // Apply collection filter if selected
    if (selectedCollectionId) {
        const selectedCollection = collections.find(c => c.id === selectedCollectionId);
        const paperIds = selectedCollection?.paper_ids || [];
        if (paperIds.length > 0) {
            const collectionPaperIds = new Set(paperIds);
            reviewedPapers = reviewedPapers.filter(p => collectionPaperIds.has(p.id));
        }
    }

    const toggleExpand = (id: string) => {
        setExpandedPapers(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const handleEditNotes = (paper: Paper) => {
        setEditingPaper(paper);
        setNotes(paper.notes || "");
    };

    const handleSaveNotes = async () => {
        if (!editingPaper) return;
        try {
            await updatePaper(editingPaper.id, { notes });
            onUpdate();
            setEditingPaper(null);
        } catch (e) {
            console.error("Failed to save notes", e);
            alert("Failed to save notes");
        }
    };

    const downloadCSV = () => {
        const headers = ["Paper Name", "Title", "Authors", "Summary", "Notes"];
        const rows = reviewedPapers.map((p) => {
            const summaryText = p.global_summary || "No global summary";

            return [
                `"${p.filename}"`,
                `"${(p.title || "Unknown").replace(/"/g, '""')}"`,
                `"${(p.authors || "Unknown").replace(/"/g, '""')}"`,
                `"${summaryText.replace(/"/g, '""')}"`,
                `"${(p.notes || "").replace(/"/g, '""')}"`,
            ].join(",");
        });

        const csvContent = "data:text/csv;charset=utf-8," + headers.join(",") + "\n" + rows.join("\n");

        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", "paper_reviews.csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const renderAuthors = (authors: string | undefined) => {
        if (!authors || authors === "Unknown") return "Not Available";
        try {
            const parsed = JSON.parse(authors);
            if (Array.isArray(parsed)) return parsed.join(", ");
        } catch (e) { }
        return authors;
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center bg-white/50 p-6 rounded-2xl border border-[#F1E9D2] mb-8">
                <div className="flex items-center gap-4">
                    <h2 className="text-2xl font-bold text-[#1A365D]">Literature Review</h2>
                    {collections.length > 0 && (
                        <Select value={selectedCollectionId || "all"} onValueChange={(val) => setSelectedCollectionId(val === "all" ? null : val)}>
                            <SelectTrigger className="w-[240px] border-2 border-[#D4AF37]/30 bg-white hover:bg-[#FDFBF7] hover:border-[#D4AF37] rounded-xl font-bold text-sm shadow-sm transition-all">
                                <FolderOpen className="h-4 w-4 mr-2 text-[#D4AF37]" />
                                <SelectValue placeholder="Filter by collection" />
                            </SelectTrigger>
                            <SelectContent className="rounded-xl border-2 border-[#D4AF37]/30 z-60 bg-white shadow-2xl">
                                <SelectItem value="all" className="font-bold text-[#1A365D]">All Papers</SelectItem>
                                {collections.map((collection) => (
                                    <SelectItem key={collection.id} value={collection.id} className="font-medium">
                                        {collection.name} ({collection.paper_count || 0})
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    )}
                </div>
                <Button
                    variant="outline"
                    onClick={downloadCSV}
                    disabled={reviewedPapers.length === 0}
                    className="border-[#F1E9D2] hover:bg-[#FDFBF7] text-[#1A365D] font-bold rounded-xl"
                >
                    <Download className="mr-2 h-4 w-4" />
                    Export Findings (CSV)
                </Button>
            </div>

            {reviewedPapers.length === 0 ? (
                <div className="text-center py-20 bg-card-yellow rounded-2xl border border-dashed border-[#F1E9D2]">
                    <p className="text-slate-500">
                        No papers reviewed yet. Extract a summary in the Documents tab to see it here.
                    </p>
                </div>
            ) : (
                <div className="space-y-4">
                    {reviewedPapers.map((paper) => {
                        const isExpanded = expandedPapers.has(paper.id);

                        // FALLBACK LOGIC: If global_summary is missing, use top points from section summaries
                        let summaryContent = paper.global_summary;
                        if (!summaryContent && paper.section_summaries && paper.section_summaries.length > 0) {
                            summaryContent = paper.section_summaries
                                .filter(s => s.section_name.toLowerCase() !== 'references')
                                .map(s => s.summary)
                                .join('\n');
                        }

                        return (
                            <div
                                key={paper.id}
                                className={`bg-white rounded-2xl border transition-all duration-300 overflow-hidden shadow-sm ${isExpanded ? 'border-[#D4AF37] ring-1 ring-[#D4AF37]/20' : 'border-[#F1E9D2] hover:border-[#D4AF37]/50 hover:shadow-md'}`}
                            >
                                {/* Collapsed Row / Trigger */}
                                <div
                                    className={`flex items-center justify-between p-5 cursor-pointer select-none transition-colors ${isExpanded ? 'bg-[#FDFBF7]' : 'hover:bg-[#FDFBF7]/50'}`}
                                    onClick={() => toggleExpand(paper.id)}
                                >
                                    <h3 className={`text-base font-extrabold tracking-tight transition-colors flex-1 ${isExpanded ? 'text-[#D4AF37]' : 'text-[#1A365D]'}`}>
                                        {paper.title || paper.filename}
                                    </h3>
                                    <div className={`transition-transform duration-300 transform ${isExpanded ? 'rotate-180' : ''}`}>
                                        <ChevronDown className={`h-5 w-5 ${isExpanded ? 'text-[#D4AF37]' : 'text-slate-300'}`} />
                                    </div>
                                </div>

                                {/* Expanded Content */}
                                {isExpanded && (
                                    <div className="border-t border-[#F1E9D2]/50 animate-in slide-in-from-top-2 duration-300">
                                        <div className="grid grid-cols-[220px_1fr_300px] w-full bg-[#FCF9F1]/30">
                                            {/* Header Row */}
                                            <div className="col-span-3 grid grid-cols-[220px_1fr_300px] border-b border-[#F1E9D2]/50 bg-[#F1E9D2]/20">
                                                <div className="px-8 py-3 text-[10px] font-extrabold text-[#1A365D] uppercase tracking-widest border-r border-[#F1E9D2]/50">Document</div>
                                                <div className="px-10 py-3 text-[10px] font-extrabold text-[#1A365D] uppercase tracking-widest border-r border-[#F1E9D2]/50">Global Summary</div>
                                                <div className="px-8 py-3 text-[10px] font-extrabold text-[#1A365D] uppercase tracking-widest">Research Notes</div>
                                            </div>

                                            {/* Content Columns */}
                                            <div className="p-8 border-r border-[#F1E9D2]/50 space-y-6">
                                                <div>
                                                    <div className="text-[10px] text-slate-400 font-bold uppercase mb-2">Filename</div>
                                                    <div className="font-bold text-[#1A365D] text-xs break-all leading-tight bg-white p-3 rounded-lg border border-[#F1E9D2]/30 shadow-sm">
                                                        {paper.filename}
                                                    </div>
                                                </div>
                                                <div className="pt-4 border-t border-[#F1E9D2]/30">
                                                    <div className="text-[10px] text-slate-400 font-bold uppercase mb-2">Authors</div>
                                                    <div className="text-[11px] text-slate-600 italic font-medium leading-relaxed bg-white/50 p-3 rounded-lg">
                                                        {renderAuthors(paper.authors)}
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="p-10 border-r border-[#F1E9D2]/50 bg-white/40">
                                                {summaryContent ? (
                                                    <div className="space-y-4">
                                                        <ul className="text-[13px] space-y-5 text-slate-700">
                                                            {summaryContent.split(/\r?\n/).filter(p => {
                                                                const clean = p.replace(/^[ \t]*[•\-*–—\d\.:]+[ \t]*/, '').trim();
                                                                if (!clean || clean.length < 5) return false;
                                                                if (clean.match(/^(here (is|are)|summary|global synthesis|key points|findings|overview)/i)) return false;
                                                                return true;
                                                            }).slice(0, 10).map((point, i) => (
                                                                <li key={i} className="flex gap-4 leading-relaxed group">
                                                                    <div className="mt-1.5 shrink-0">
                                                                        <div className="h-1.5 w-1.5 rounded-full bg-[#D4AF37] group-hover:scale-125 transition-transform" />
                                                                    </div>
                                                                    <span className="group-hover:text-black transition-colors">{point.replace(/^[ \t]*[•\-*–—\d\.:]+[ \t]*/, '').trim().replace(/\s+/g, ' ')}</span>
                                                                </li>
                                                            ))}
                                                        </ul>
                                                    </div>
                                                ) : (
                                                    <div className="flex flex-col items-center justify-center h-full py-10 opacity-40">
                                                        <p className="text-sm text-slate-400 italic">Analysis in progress or not available.</p>
                                                    </div>
                                                )}
                                            </div>

                                            <div className="p-8">
                                                <div
                                                    onClick={(e) => { e.stopPropagation(); handleEditNotes(paper); }}
                                                    className="cursor-pointer group relative p-6 rounded-2xl bg-white hover:bg-[#FDFBF7] border border-[#F1E9D2]/60 hover:border-[#D4AF37]/50 transition-all min-h-[220px] shadow-sm flex flex-col"
                                                >
                                                    <div className="flex items-center gap-2 mb-3 opacity-30">
                                                        <FileEdit className="h-3 w-3" />
                                                        <span className="text-[10px] font-bold uppercase tracking-wider">Editor</span>
                                                    </div>
                                                    {paper.notes ? (
                                                        <p className="text-[13px] text-slate-700 whitespace-pre-wrap leading-relaxed">
                                                            {paper.notes}
                                                        </p>
                                                    ) : (
                                                        <p className="text-[13px] text-slate-300 italic leading-relaxed">
                                                            Click here to capture your personal insights, key takeaways, or potential research gaps...
                                                        </p>
                                                    )}
                                                    <div className="absolute bottom-4 right-4 h-8 w-8 rounded-full bg-[#D4AF37]/5 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all">
                                                        <FileEdit className="h-4 w-4 text-[#D4AF37]" />
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            <Modal
                isOpen={!!editingPaper}
                onClose={() => setEditingPaper(null)}
                title={`Notes for ${editingPaper?.filename}`}
                footer={
                    <>
                        <Button variant="ghost" className="text-slate-400 font-bold" onClick={() => setEditingPaper(null)}>
                            Discard
                        </Button>
                        <Button className="bg-[#1A365D] hover:bg-[#2C5282] text-white px-8 rounded-xl" onClick={handleSaveNotes}>
                            Save Insights
                        </Button>
                    </>
                }
            >
                <div className="py-2">
                    <Textarea
                        value={notes}
                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setNotes(e.target.value)}
                        placeholder="Write your findings, critiques, or ideas here..."
                        className="min-h-[200px]"
                    />
                </div>
            </Modal>
        </div>
    );
}
