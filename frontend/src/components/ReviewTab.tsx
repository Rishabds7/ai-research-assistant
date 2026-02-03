"use client";

import { Paper, updatePaper } from "@/lib/api";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Download, FileEdit, X } from "lucide-react";
import { useState } from "react";
import { Textarea } from "@/components/ui/textarea";

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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg overflow-hidden animate-in zoom-in duration-200">
                <div className="flex items-center justify-between p-4 border-b">
                    <h3 className="text-lg font-bold text-slate-900">{title}</h3>
                    <button onClick={onClose} className="p-1 rounded-full hover:bg-slate-100 transition-colors">
                        <X className="h-5 w-5 text-slate-500" />
                    </button>
                </div>
                <div className="p-6">{children}</div>
                {footer && <div className="flex justify-end gap-3 p-4 bg-slate-50 border-t">{footer}</div>}
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
            <div className="flex justify-between items-center">
                <h2 className="text-xl font-bold text-slate-900">Literature Review</h2>
                <Button
                    variant="outline"
                    onClick={downloadCSV}
                    disabled={reviewedPapers.length === 0}
                >
                    <Download className="mr-2 h-4 w-4" />
                    Download CSV
                </Button>
            </div>

            {reviewedPapers.length === 0 ? (
                <div className="text-center py-20 bg-white rounded-lg border border-dashed border-slate-300">
                    <p className="text-slate-500">
                        No papers reviewed yet. Summarize a paper to see it here.
                    </p>
                </div>
            ) : (
                <div className="bg-white rounded-lg border overflow-hidden">
                    <Table>
                        <TableHeader>
                            <TableRow className="bg-slate-50">
                                <TableHead className="w-[200px] font-bold">Paper Name</TableHead>
                                <TableHead className="font-bold">Summary</TableHead>
                                <TableHead className="w-[250px] font-bold">Notes</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {reviewedPapers.map((paper) => (
                                <TableRow key={paper.id}>
                                    <TableCell className="align-top py-4">
                                        <div className="font-bold text-slate-900 mb-1 leading-tight break-words">
                                            {paper.filename}
                                        </div>
                                        {paper.title && (
                                            <div className="text-[11px] text-slate-500 leading-snug mt-2 pt-2 border-t border-slate-100">
                                                <span className="font-bold text-slate-400 uppercase tracking-tight">TITLE: </span>
                                                <span className="italic">{paper.title}</span>
                                            </div>
                                        )}
                                    </TableCell>
                                    <TableCell className="align-top py-4">
                                        {paper.global_summary ? (
                                            <ul className="text-xs space-y-2 text-slate-600">
                                                {paper.global_summary.split(/\n|•|\*/).filter(p => {
                                                    const clean = p.trim();
                                                    if (!clean) return false;
                                                    // Filter out common LLM intro/outro phrases
                                                    if (clean.toLowerCase().includes("here is a summary")) return false;
                                                    if (clean.toLowerCase().includes("bullet points")) return false;
                                                    if (clean.toLowerCase().includes("concise summary")) return false;
                                                    if (clean.length < 5) return false;
                                                    return true;
                                                }).map((point, i) => (
                                                    <li key={i} className="flex gap-2 leading-relaxed">
                                                        <span className="text-blue-500 font-bold shrink-0">•</span>
                                                        <span>{point.trim()}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        ) : (
                                            <p className="text-xs text-slate-400 italic">No global summary generated. Click "Summarize" in the Papers tab.</p>
                                        )}
                                    </TableCell>
                                    <TableCell className="align-top">
                                        <div
                                            onClick={() => handleEditNotes(paper)}
                                            className="cursor-pointer group relative p-2 rounded hover:bg-slate-50 border border-transparent hover:border-slate-200 transition-all min-h-[60px]"
                                        >
                                            {paper.notes ? (
                                                <p className="text-xs text-slate-700 whitespace-pre-wrap">
                                                    {paper.notes}
                                                </p>
                                            ) : (
                                                <p className="text-xs text-slate-400 italic">
                                                    Click to add notes...
                                                </p>
                                            )}
                                            <FileEdit className="absolute top-1 right-1 h-3 w-3 text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity" />
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
                        <Button variant="outline" onClick={() => setEditingPaper(null)}>
                            Cancel
                        </Button>
                        <Button onClick={handleSaveNotes}>Save Notes</Button>
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
