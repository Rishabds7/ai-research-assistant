/**
 * MAIN LANDING PAGE
 * Project: Research Assistant
 * File: frontend/src/app/page.tsx
 * 
 * This is the primary entry point for the user interface.
 * It coordinates:
 * 1. File Uploading (parallel processing).
 * 2. Navigation between 'Papers' (list view) and 'Review' (side-by-side reading).
 * 3. Bulk actions (Delete All).
 */
"use client";

import { useState, useEffect, useRef } from "react";
import { getPapers, uploadPaper, Paper, deleteAllPapers } from "@/lib/api";
import { PaperItem } from "@/components/PaperItem";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, UploadCloud, Trash2, X, AlertTriangle } from "lucide-react";
import { ReviewTab } from "@/components/ReviewTab";

export default function Home() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [uploadingCount, setUploadingCount] = useState(0);
  const [rejectedMessages, setRejectedMessages] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchPapers = async () => {
    try {
      const data = await getPapers();
      setPapers(data);
    } catch (e) {
      console.error("Failed to fetch papers", e);
    }
  };

  useEffect(() => {
    fetchPapers();
  }, []);

  const handleReject = (msg: string) => {
    setRejectedMessages(prev => [...prev, msg]);
    // Auto-remove notification after 3 seconds
    setTimeout(() => {
      setRejectedMessages(prev => prev.slice(1));
    }, 4000);
  };

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFiles = Array.from(e.target.files);

      // Duplicate Check
      const newFiles = selectedFiles.filter(file =>
        !papers.some(p => p.filename === file.name)
      );

      if (newFiles.length === 0) {
        e.target.value = '';
        return;
      }

      setUploadingCount(prev => prev + newFiles.length);

      await Promise.all(newFiles.map(async (file) => {
        try {
          const res = await uploadPaper(file);
          const newPaper = { ...res.paper, uploadTaskId: res.task_id };
          setPapers((prev) => [newPaper, ...prev]);
        } catch (e: any) {
          console.error(`Upload failed: ${file.name}`, e);
          if (e.response?.data?.error) alert(e.response.data.error);
          else alert(`Connection issue while uploading ${file.name}.`);
        } finally {
          setUploadingCount(prev => Math.max(0, prev - 1));
        }
      }));

      e.target.value = '';
    }
  };

  const handleDeleteAll = async () => {
    if (confirm("Are you sure you want to delete ALL papers?")) {
      try {
        await deleteAllPapers();
        fetchPapers();
      } catch (e) {
        console.error("Delete all failed", e);
      }
    }
  };

  return (
    <main className="min-h-screen bg-[#F8F5EE] py-12 px-4 md:px-8 lg:px-12 relative overflow-hidden">
      {/* Floating Rejection Notifications */}
      <div className="fixed top-8 right-8 z-[100] space-y-4 pointer-events-none max-w-sm">
        {rejectedMessages.map((msg, idx) => (
          <div key={idx} className="bg-red-600 text-white px-6 py-4 rounded-2xl shadow-2xl border-2 border-red-500/50 flex items-center gap-4 animate-in slide-in-from-right-10 duration-500 pointer-events-auto">
            <AlertTriangle className="h-6 w-6 text-yellow-300 shrink-0" />
            <div>
              <p className="font-bold text-sm">Document Rejected</p>
              <p className="text-xs opacity-90 leading-tight">{msg}</p>
            </div>
            <button
              onClick={() => setRejectedMessages(prev => prev.filter((_, i) => i !== idx))}
              className="ml-2 hover:bg-white/20 p-1 rounded-full transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>

      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center bg-white/60 backdrop-blur-md p-8 rounded-[32px] border border-white shadow-xl">
          <div className="flex items-center gap-6">
            <div className="relative group">
              <div className="absolute -inset-1 bg-gradient-to-r from-[#D4AF37] to-[#1A365D] rounded-2xl blur opacity-25 group-hover:opacity-50 transition duration-1000"></div>
              <img
                src="/logo.png"
                alt="PaperDigest AI Logo"
                className="relative h-20 w-20 object-contain logo-animate rounded-2xl"
              />
            </div>
            <div>
              <h1 className="text-5xl font-extrabold tracking-tight text-[#1A365D] mb-1">
                PaperDigest <span className="text-[#D4AF37]">AI</span>
              </h1>
              <p className="text-slate-500 font-semibold tracking-wide flex items-center gap-2">
                <span className="w-8 h-[2px] bg-[#D4AF37]"></span>
                Synthesizing deep research into actionable insights
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {papers.length > 0 && (
              <Button
                variant="ghost"
                onClick={handleDeleteAll}
                className="text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors h-14 w-14 rounded-2xl"
              >
                <Trash2 className="h-6 w-6" />
              </Button>
            )}

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              multiple
              className="hidden"
              onChange={handleFileChange}
            />
            <Button
              onClick={handleButtonClick}
              disabled={uploadingCount > 10}
              className="bg-[#1A365D] hover:bg-[#0F2342] text-white px-8 py-7 rounded-2xl shadow-2xl shadow-blue-900/20 transition-all hover:scale-[1.02] active:scale-[0.98] border-b-4 border-[#081529]"
            >
              {uploadingCount > 0 ? (
                <>
                  <Loader2 className="mr-3 h-6 w-6 animate-spin" />
                  <span className="text-xl font-bold italic">Analyzing {uploadingCount}...</span>
                </>
              ) : (
                <>
                  <UploadCloud className="mr-3 h-6 w-6" />
                  <span className="text-xl font-bold">Upload Documents</span>
                </>
              )}
            </Button>
          </div>
        </div>

        <Tabs defaultValue="papers" className="w-full mt-12">
          <TabsList className="flex w-full max-w-md mx-auto bg-[#1A365D]/5 p-2 rounded-2xl mb-12 border border-[#1A365D]/10">
            <TabsTrigger
              value="papers"
              className="flex-1 py-4 rounded-xl data-[state=active]:bg-[#1A365D] data-[state=active]:text-white shadow-lg transition-all text-sm font-bold uppercase tracking-widest"
            >
              📄 Documents
            </TabsTrigger>
            <TabsTrigger
              value="review"
              className="flex-1 py-4 rounded-xl data-[state=active]:bg-[#1A365D] data-[state=active]:text-white shadow-lg transition-all text-sm font-bold uppercase tracking-widest"
            >
              📋 AI Review
            </TabsTrigger>
          </TabsList>

          <TabsContent value="papers" className="space-y-8 min-h-[400px]">
            {papers.length === 0 && uploadingCount === 0 ? (
              <div
                className="text-center py-40 bg-white/40 backdrop-blur-sm rounded-[48px] border-4 border-dashed border-[#F1E9D2] group hover:border-[#D4AF37] transition-all cursor-pointer shadow-inner"
                onClick={handleButtonClick}
              >
                <div className="bg-white p-6 rounded-3xl w-24 h-24 flex items-center justify-center mx-auto mb-8 shadow-xl group-hover:scale-110 group-hover:rotate-3 transition-all duration-500">
                  <UploadCloud className="h-12 w-12 text-[#1A365D]" />
                </div>
                <h3 className="text-3xl font-black text-[#1A365D]">Your Library is Empty</h3>
                <p className="text-slate-500 mt-4 text-lg font-medium">Upload your research PDFs to begin deep AI synthesis</p>
                <div className="mt-8 text-[#D4AF37] font-bold flex items-center justify-center gap-2 opacity-50 group-hover:opacity-100">
                  <span>Click anywhere to start</span>
                  <Loader2 className="h-4 w-4" />
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-6">
                {papers.map((paper) => (
                  <PaperItem
                    key={paper.id}
                    paper={paper}
                    onUpdate={fetchPapers}
                    onReject={handleReject}
                  />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="review">
            <ReviewTab papers={papers} onUpdate={fetchPapers} />
          </TabsContent>
        </Tabs>
      </div>
    </main>
  );
}
