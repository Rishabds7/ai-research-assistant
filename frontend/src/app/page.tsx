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

import { useState, useEffect } from "react";
import { getPapers, uploadPaper, Paper, deleteAllPapers, ingestArxiv } from "@/lib/api";
import { PaperItem } from "@/components/PaperItem";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input"; // We'll use standard input for file upload
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, UploadCloud, Trash2, Link } from "lucide-react";
import { ReviewTab } from "@/components/ReviewTab";
import { CollectionsTab } from '@/components/CollectionsTab';

export default function Home() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [uploadingCount, setUploadingCount] = useState(0);
  const [arxivUrl, setArxivUrl] = useState("");
  const [isIngesting, setIsIngesting] = useState(false);

  const fetchPapers = async () => {
    try {
      const data = await getPapers();
      setPapers(prev => {
        // 1. Identify existing optimistic placeholders
        const placeholders = prev.filter(p => p.id.toString().startsWith('temp-'));

        // 2. Filter out placeholders that have already been uploaded (matched by filename)
        const activePlaceholders = placeholders.filter(ph =>
          !data.some((d: Paper) => d.filename === ph.filename)
        );

        // 3. Combine and sort
        const combined = [...activePlaceholders, ...data];

        // Sort: Real papers by uploaded_at, Placeholders at the very top.
        return combined.sort((a, b) => {
          if (a.id.toString().startsWith('temp-')) return -1;
          if (b.id.toString().startsWith('temp-')) return 1;
          return new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime();
        });
      });
    } catch (e) {
      console.error("Failed to fetch papers", e);
    }
  };

  useEffect(() => {
    fetchPapers();
  }, []);


  const handleButtonClick = () => {
    const input = document.getElementById('file-upload-input') as HTMLInputElement;
    if (input) input.click();
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

      // OPTIMISTIC UPDATES: Show "ghost" cards immediately
      const placeholders = newFiles.map(file => ({
        id: `temp-${file.name}-${Date.now()}`,
        filename: file.name,
        processed: false,
        uploaded_at: new Date().toISOString(),
        file: '',
        title: 'Extracting...',
      } as Paper));

      setPapers(prev => [...placeholders, ...prev]);

      await Promise.all(newFiles.map(async (file, idx) => {
        try {
          const res = await uploadPaper(file);
          const newPaper = { ...res.paper, uploadTaskId: res.task_id };
          // Replace placeholder with real paper data
          setPapers(prev => prev.map(p => p.id === placeholders[idx].id ? newPaper : p));
        } catch (e: any) {
          console.error(`Upload failed: ${file.name}`, e);
          // Remove placeholder on failure
          setPapers(prev => prev.filter(p => p.id !== placeholders[idx].id));
          if (e.response?.data?.error) alert(e.response.data.error);
          else alert(`Connection issue while uploading ${file.name}.`);
        } finally {
          setUploadingCount(prev => Math.max(0, prev - 1));
        }
      }));

      e.target.value = '';
    }
  };

  const handleArxivSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!arxivUrl.trim() || isIngesting) return;

    setIsIngesting(true);
    const tempId = `temp-arxiv-${Date.now()}`;

    // Optimistic Update
    const placeholder: Paper = {
      id: tempId,
      filename: "Fetching from ArXiv...",
      processed: false,
      uploaded_at: new Date().toISOString(),
      file: '',
      title: 'Connecting to ArXiv...',
    } as Paper;

    setPapers(prev => [placeholder, ...prev]);

    try {
      const res = await ingestArxiv(arxivUrl);
      const newPaper = { ...res.paper, uploadTaskId: res.task_id };
      setPapers(prev => prev.map(p => p.id === tempId ? newPaper : p));
      setArxivUrl("");
    } catch (e: any) {
      console.error("ArXiv ingest failed", e);
      setPapers(prev => prev.filter(p => p.id !== tempId));
      alert(e.response?.data?.error || "Failed to ingest paper from ArXiv. Check the URL/ID.");
    } finally {
      setIsIngesting(false);
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
    <main className="min-h-screen bg-background p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        <div className="flex justify-between items-center bg-white/70 backdrop-blur-md p-6 rounded-3xl border border-[#F1E9D2] shadow-xl shadow-blue-900/5 transition-all duration-500 hover:shadow-2xl hover:shadow-blue-900/10">
          <div className="flex items-center gap-6">
            <div className="relative group">
              <div className="absolute -inset-2 bg-linear-to-r from-[#D4AF37] to-[#1A365D] rounded-2xl blur-md opacity-20 group-hover:opacity-40 transition duration-1000"></div>
              <img
                src="/logo.png"
                alt="PaperDigest AI Logo"
                className="relative h-16 w-16 object-contain logo-animate logo-glow rounded-xl"
              />
            </div>
            <div className="space-y-0.5">
              <h1 className="text-4xl font-extrabold tracking-tight text-[#1A365D]">
                PaperDigest <span className="text-[#D4AF37]">AI</span>
              </h1>
              <p className="text-slate-500 font-bold uppercase text-[10px] tracking-[0.3em] opacity-80">
                AI-Powered Research Intelligence
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <form onSubmit={handleArxivSubmit} className="flex items-center bg-white border border-[#F1E9D2] p-1.5 rounded-2xl shadow-inner-sm mr-2 transition-all focus-within:ring-2 focus-within:ring-[#D4AF37]/20 group/arxiv">
              <div className="flex items-center gap-2 px-3 text-slate-400 group-focus-within/arxiv:text-[#D4AF37] transition-colors">
                <Link className="h-4 w-4" />
              </div>
              <Input
                placeholder="ArXiv URL or ID..."
                className="border-none bg-transparent focus-visible:ring-0 w-44 text-sm font-medium"
                value={arxivUrl}
                onChange={(e) => setArxivUrl(e.target.value)}
                disabled={isIngesting}
              />
              <Button
                type="submit"
                variant="ghost"
                size="sm"
                className="rounded-xl h-9 px-4 font-extrabold text-[#1A365D] hover:bg-[#D4AF37] hover:text-white transition-all active:scale-90"
                disabled={isIngesting || !arxivUrl}
              >
                {isIngesting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Fetch"}
              </Button>
            </form>

            <div className="text-[#1A365D]/20 font-black text-[9px] tracking-[0.4em]">OR</div>

            <input
              id="file-upload-input"
              type="file"
              accept=".pdf"
              multiple
              className="hidden"
              onChange={handleFileChange}
            />
            <Button
              onClick={handleButtonClick}
              disabled={uploadingCount > 10}
              className="bg-[#1A365D] hover:bg-[#0F172A] text-white px-8 h-14 rounded-2xl shadow-xl shadow-[#1A365D]/20 transition-all hover:scale-[1.03] active:scale-[0.97] font-bold"
            >
              {uploadingCount > 0 ? (
                <>
                  <Loader2 className="mr-3 h-5 w-5 animate-spin text-[#D4AF37]" />
                  Processing {uploadingCount}...
                </>
              ) : (
                <>
                  <UploadCloud className="mr-3 h-6 w-6" />
                  <span className="text-base">Upload Research</span>
                </>
              )}
            </Button>
          </div>
        </div>

        <Tabs defaultValue="papers" className="w-full">
          <div className="flex items-center justify-between mb-8 animate-in fade-in slide-in-from-bottom-2 duration-700">
            <TabsList className="bg-white/40 backdrop-blur-sm p-1.5 rounded-2xl border border-[#F1E9D2]/80 shadow-sm">
              <TabsTrigger
                value="papers"
                className="px-10 py-3 rounded-xl data-[state=active]:bg-[#1A365D] data-[state=active]:text-white data-[state=active]:shadow-lg transition-all font-extrabold tracking-tight group"
              >
                <div className="flex items-center gap-2">
                  <span className="opacity-70 group-data-[state=active]:opacity-100">📄</span>
                  Library
                </div>
              </TabsTrigger>
              <TabsTrigger
                value="review"
                className="px-10 py-3 rounded-xl data-[state=active]:bg-[#D4AF37] data-[state=active]:text-white data-[state=active]:shadow-lg transition-all font-extrabold tracking-tight group"
              >
                <div className="flex items-center gap-2">
                  <span className="opacity-70 group-data-[state=active]:opacity-100">📋</span>
                  Literature Review
                </div>
              </TabsTrigger>
              <TabsTrigger
                value="collections"
                className="px-10 py-3 rounded-xl data-[state=active]:bg-[#10B981] data-[state=active]:text-white data-[state=active]:shadow-lg transition-all font-extrabold tracking-tight group"
              >
                <div className="flex items-center gap-2">
                  <span className="opacity-70 group-data-[state=active]:opacity-100">📁</span>
                  Collections
                </div>
              </TabsTrigger>
            </TabsList>

            {papers.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleDeleteAll}
                className="border-red-100 text-red-400 hover:text-red-600 hover:bg-red-50 hover:border-red-200 transition-all font-bold px-4 h-10 rounded-xl flex items-center gap-2"
              >
                <Trash2 className="h-4 w-4" />
                Delete All
              </Button>
            )}
          </div>

          <TabsContent value="papers" className="space-y-6">
            {papers.length === 0 ? (
              <div
                className="text-center py-32 bg-card-yellow rounded-3xl border-2 border-dashed border-[#F1E9D2] group hover:border-[#D4AF37] transition-colors cursor-pointer"
                onClick={handleButtonClick}
              >
                <div className="bg-white p-4 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4 shadow-sm group-hover:scale-110 transition-transform">
                  <UploadCloud className="h-8 w-8 text-[#1A365D]" />
                </div>
                <h3 className="text-xl font-semibold text-[#1A365D]">No documents yet</h3>
                <p className="text-slate-500 mt-2">Upload your research PDFs to begin AI analysis</p>
              </div>
            ) : (
              papers.map((paper) => (
                <PaperItem key={paper.id} paper={paper} onUpdate={fetchPapers} />
              ))
            )}
          </TabsContent>

          <TabsContent value="review">
            <ReviewTab papers={papers} onUpdate={fetchPapers} />
          </TabsContent>

          <TabsContent value="collections" className="space-y-6">
            <CollectionsTab papers={papers} onUpdate={fetchPapers} />
          </TabsContent>
        </Tabs>
      </div>
    </main >
  );
}
