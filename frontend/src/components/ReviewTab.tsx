"use client";

import { Paper, updatePaper } from "@/lib/api";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { Button } from "./ui/button";
import { Download, FileEdit, X, ChevronDown } from "lucide-react";
import React, { useState } from "react";
import { Textarea } from "./ui/textarea";

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

    // Only show papers that have been summarized (Stage 2 complete)
    const reviewedPapers = papers.filter(
        (p) => (p.section_summaries && p.section_summaries.length > 0) || p.global_summary
    );

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
            <div className="flex justify-between items-center bg-white/50 p-4 rounded-xl border border-[#F1E9D2]">
                <h2 className="text-xl font-bold text-[#1A365D]">Literature Review</h2>
                <Button
                    variant="outline"
                    onClick={downloadCSV}
                    disabled={reviewedPapers.length === 0}
                    className="border-[#F1E9D2] hover:bg-[#FDFBF7] text-[#1A365D]"
                >
                    <Download className="mr-2 h-4 w-4" />
                    Export Findings
                </Button>
            </div>

            {reviewedPapers.length === 0 ? (
                <div className="text-center py-20 bg-card-yellow rounded-2xl border border-dashed border-[#F1E9D2]">
                    <p className="text-slate-500">
                        No papers reviewed yet. Extract a summary in the Documents tab to see it here.
                    </p>
                </div>
            ) : (
                <div className="bg-white rounded-2xl border border-[#F1E9D2] overflow-hidden shadow-sm">
                    <Table>
                        <TableHeader>
                            <TableRow className="bg-[#F1E9D2]/20 hover:bg-[#F1E9D2]/20 border-b border-[#F1E9D2]">
                                <TableHead className="font-extrabold text-[#1A365D] py-4 px-6 text-sm uppercase tracking-widest">
                                    Literature Review Synthesis
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
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
                                    <React.Fragment key={paper.id}>
                                        <TableRow
                                            className={`cursor-pointer border-b border-[#F1E9D2]/30 transition-all ${isExpanded ? 'bg-[#FDFBF7]' : 'hover:bg-[#FDFBF7]/50'}`}
                                            onClick={() => toggleExpand(paper.id)}
                                        >
                                            <TableCell className="py-5 px-6">
                                                <div className="flex items-center gap-4">
                                                    <div className={`transition-transform duration-300 transform ${isExpanded ? 'rotate-180' : ''}`}>
                                                        <ChevronDown className={`h-5 w-5 ${isExpanded ? 'text-[#D4AF37]' : 'text-slate-300'}`} />
                                                    </div>
                                                    <span className={`text-base font-extrabold tracking-tight transition-colors ${isExpanded ? 'text-[#D4AF37]' : 'text-[#1A365D]'}`}>
                                                        {paper.title || paper.filename}
                                                    </span>
                                                </div>
                                            </TableCell>
                                        </TableRow>

                                        {isExpanded && (
                                            <TableRow className="bg-white hover:bg-white border-b border-[#F1E9D2] last:border-0">
                                                <TableCell className="p-0">
                                                    <div className="p-8 animate-in slide-in-from-top-4 duration-500">
                                                        <div className="grid grid-cols-[200px_1fr_280px] gap-8 bg-[#FDFBF7]/30 p-8 rounded-3xl border border-[#F1E9D2]/50 shadow-sm">
                                                            {/* Column 1: Document Info */}
                                                            <div className="space-y-6">
                                                                <div>
                                                                    <h4 className="text-[10px] font-extrabold text-[#D4AF37] uppercase tracking-widest mb-3">Document Info:</h4>
                                                                    <div className="bg-white p-4 rounded-xl border border-[#F1E9D2]/40 shadow-sm space-y-4">
                                                                        <div>
                                                                            <div className="text-[10px] text-slate-400 font-bold uppercase mb-1">Filename:</div>
                                                                            <div className="font-bold text-[#1A365D] text-xs break-all leading-tight">
                                                                                {paper.filename}
                                                                            </div>
                                                                        </div>
                                                                        <div className="pt-3 border-t border-[#F1E9D2]/20">
                                                                            <div className="text-[10px] text-slate-400 font-bold uppercase mb-1">Authors:</div>
                                                                            <div className="text-[11px] text-slate-600 italic font-medium leading-snug">
                                                                                {renderAuthors(paper.authors)}
                                                                            </div>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            </div>

                                                            {/* Column 2: AI Synthesis */}
                                                            <div className="space-y-4">
                                                                <h4 className="text-[10px] font-extrabold text-[#D4AF37] uppercase tracking-widest mb-3">AI Synthesis:</h4>
                                                                {summaryContent ? (
                                                                    <div className="bg-white p-6 rounded-2xl border border-[#F1E9D2]/40 shadow-sm italic">
                                                                        <ul className="text-[13px] space-y-4 text-slate-700">
                                                                            {summaryContent.split(/\r?\n/).filter(p => {
                                                                                const clean = p.replace(/^[ \t]*[•\-*–—\d\.:]+[ \t]*/, '').trim();
                                                                                if (!clean || clean.length < 5) return false;
                                                                                if (clean.match(/^(here (is|are)|summary|global synthesis|key points|findings|overview)/i)) return false;
                                                                                return true;
                                                                            }).slice(0, 8).map((point, i) => (
                                                                                <li key={i} className="flex gap-4 leading-relaxed">
                                                                                    <span className="text-[#D4AF37] font-extrabold shrink-0 mt-0.5">◇</span>
                                                                                    <span>{point.replace(/^[ \t]*[•\-*–—\d\.:]+[ \t]*/, '').trim().replace(/\s+/g, ' ')}</span>
                                                                                </li>
                                                                            ))}
                                                                        </ul>
                                                                    </div>
                                                                ) : (
                                                                    <div className="bg-slate-50 p-6 rounded-2xl border border-dashed border-slate-200 text-center">
                                                                        <p className="text-sm text-slate-400 italic">No summary generated yet.</p>
                                                                    </div>
                                                                )}
                                                            </div>

                                                            {/* Column 3: Personal Notes */}
                                                            <div className="space-y-4">
                                                                <h4 className="text-[10px] font-extrabold text-[#D4AF37] uppercase tracking-widest mb-3">Personal Notes:</h4>
                                                                <div
                                                                    onClick={(e) => { e.stopPropagation(); handleEditNotes(paper); }}
                                                                    className="cursor-pointer group relative p-6 rounded-2xl bg-white hover:bg-[#FDFBF7] border border-[#F1E9D2]/40 hover:border-[#D4AF37]/50 transition-all min-h-[160px] shadow-sm flex flex-col"
                                                                >
                                                                    {paper.notes ? (
                                                                        <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                                                                            {paper.notes}
                                                                        </p>
                                                                    ) : (
                                                                        <p className="text-sm text-slate-300 italic">
                                                                            Click to add your insights and key takeaways from this paper...
                                                                        </p>
                                                                    )}
                                                                    <FileEdit className="absolute bottom-4 right-4 h-4 w-4 text-[#D4AF37] opacity-0 group-hover:opacity-100 transition-opacity" />
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </TableCell>
                                            </TableRow>
                                        )}
                                    </React.Fragment >
                                );
                            })}
                        </TableBody>
                    </Table>
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
