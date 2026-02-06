"use client";

import { Paper, updatePaper } from "../lib/api";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { Button } from "./ui/button";
import { Download, FileEdit, X } from "lucide-react";
import { useState } from "react";
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
    const [editingPaper, setEditingPaper] = useState<Paper | null>(null);
    const [notes, setNotes] = useState("");

    // Only show papers that have been summarized
    const reviewedPapers = papers.filter(
        (p) => p.section_summaries && p.section_summaries.length > 0
    );

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
                <div className="text-center py-20 bg-[var(--card-yellow)] rounded-2xl border border-dashed border-[#F1E9D2]">
                    <p className="text-slate-500">
                        No papers reviewed yet. Extract a summary in the Documents tab to see it here.
                    </p>
                </div>
            ) : (
                <div className="bg-white rounded-2xl border border-[#F1E9D2] overflow-hidden shadow-sm">
                    <Table>
                        <TableHeader>
                            <TableRow className="bg-[#F1E9D2]/20 hover:bg-[#F1E9D2]/20">
                                <TableHead className="w-[200px] font-bold text-[#1A365D]">Document</TableHead>
                                <TableHead className="font-bold text-[#1A365D]">AI Synthesis</TableHead>
                                <TableHead className="w-[250px] font-bold text-[#1A365D]">Personal Notes</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {reviewedPapers.map((paper) => (
                                <TableRow key={paper.id} className="border-[#F1E9D2]/50 hover:bg-[#FDFBF7]/50 transition-colors">
                                    <TableCell className="align-top py-6">
                                        <div className="font-bold text-[#1A365D] mb-1 leading-tight break-words">
                                            {paper.filename}
                                        </div>
                                        {paper.title && (
                                            <div className="text-[11px] text-slate-500 leading-snug mt-3 pt-3 border-t border-[#F1E9D2]/30">
                                                <span className="font-bold text-[#D4AF37] uppercase tracking-tight">TITLE: </span>
                                                <span className="italic">{paper.title}</span>
                                            </div>
                                        )}
                                    </TableCell>
                                    <TableCell className="align-top py-6">
                                        {paper.global_summary ? (
                                            <ul className="text-xs space-y-3 text-slate-600">
                                                {paper.global_summary.split(/\r?\n/).filter(p => {
                                                    const clean = p.replace(/^[ \t]*[•\-*–—\d\.:]+[ \t]*/, '').trim();
                                                    if (!clean || clean.length < 5) return false;
                                                    // Filter out common header leftovers
                                                    if (clean.match(/^(here (is|are)|summary|global synthesis|key points|findings|overview)/i)) return false;
                                                    return true;
                                                }).map((point, i) => (
                                                    <li key={i} className="flex gap-3 leading-relaxed">
                                                        <span className="text-[#D4AF37] font-bold shrink-0">◇</span>
                                                        {/* Clean again for display */}
                                                        <span>{point.replace(/^[ \t]*[•\-*–—\d\.:]+[ \t]*/, '').trim()}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        ) : (
                                            <p className="text-xs text-slate-400 italic">No summary generated yet.</p>
                                        )}
                                    </TableCell>
                                    <TableCell className="align-top py-6">
                                        <div
                                            onClick={() => handleEditNotes(paper)}
                                            className="cursor-pointer group relative p-3 rounded-xl hover:bg-[#FDFBF7] border border-transparent hover:border-[#F1E9D2] transition-all min-h-[80px]"
                                        >
                                            {paper.notes ? (
                                                <p className="text-xs text-slate-700 whitespace-pre-wrap leading-relaxed">
                                                    {paper.notes}
                                                </p>
                                            ) : (
                                                <p className="text-xs text-slate-300 italic">
                                                    Click to add your insights...
                                                </p>
                                            )}
                                            <FileEdit className="absolute top-2 right-2 h-3.5 w-3.5 text-[#D4AF37] opacity-0 group-hover:opacity-100 transition-opacity" />
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
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
