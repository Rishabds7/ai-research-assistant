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
        <div className="flex justify-between items-center bg-white/50 backdrop-blur-sm p-6 rounded-2xl border border-[#F1E9D2] shadow-sm">
          <div className="flex items-center gap-6">
            <div className="relative group">
              <div className="absolute -inset-1 bg-linear-to-r from-[#D4AF37] to-[#1A365D] rounded-xl blur opacity-25 group-hover:opacity-50 transition duration-1000 group-hover:duration-200"></div>
              <img
                src="/logo.png"
                alt="PaperDigest AI Logo"
                className="relative h-16 w-16 object-contain logo-animate logo-glow rounded-xl"
              />
            </div>
            <div>
              <h1 className="text-4xl font-extrabold tracking-tight text-[#1A365D]">
                PaperDigest <span className="text-[#D4AF37]">AI</span>
              </h1>
              <p className="text-slate-500 font-medium tracking-wide">
                Transform research paper into actionable insights
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <form onSubmit={handleArxivSubmit} className="flex items-center bg-white border border-[#F1E9D2] p-1 rounded-xl shadow-inner-sm mr-2 overflow-hidden">
              <div className="flex items-center gap-2 px-3 text-slate-400">
                <Link className="h-4 w-4" />
              </div>
              <Input
                placeholder="ArXiv URL or ID (e.g. 2303.12345)"
                className="border-none bg-transparent focus-visible:ring-0 w-48 text-sm"
                value={arxivUrl}
                onChange={(e) => setArxivUrl(e.target.value)}
                disabled={isIngesting}
              />
              <Button
                type="submit"
                variant="ghost"
                size="sm"
                className="rounded-lg h-9 font-bold text-[#1A365D] hover:bg-[#F1E9D2]/30"
                disabled={isIngesting || !arxivUrl}
              >
                {isIngesting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Fetch"}
              </Button>
            </form>

            {papers.length > 0 && (
              <Button
                variant="ghost"
                onClick={handleDeleteAll}
                className="text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                title="Delete all papers"
              >
                <Trash2 className="h-5 w-5" />
              </Button>
            )}

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
              className="bg-[#1A365D] hover:bg-[#2C5282] text-white px-6 py-6 rounded-xl shadow-lg shadow-blue-900/10 transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              {uploadingCount > 0 ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Processing {uploadingCount}...
                </>
              ) : (
                <>
                  <UploadCloud className="mr-2 h-5 w-5" />
                  <span className="text-lg">Upload Documents</span>
                </>
              )}
            </Button>
          </div>
        </div>

        <Tabs defaultValue="papers" className="w-full">
          <TabsList className="flex w-full max-w-md mx-auto bg-[#F1E9D2]/30 p-1 rounded-xl mb-8 border border-[#F1E9D2]/50">
            <TabsTrigger
              value="papers"
              className="flex-1 py-3 rounded-lg data-[state=active]:bg-white data-[state=active]:text-[#1A365D] data-[state=active]:shadow-sm transition-all"
            >
              📄 Documents
            </TabsTrigger>
            <TabsTrigger
              value="review"
              className="flex-1 py-3 rounded-lg data-[state=active]:bg-white data-[state=active]:text-[#1A365D] data-[state=active]:shadow-sm transition-all"
            >
              📋 AI Review
            </TabsTrigger>
          </TabsList>

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
        </Tabs>
      </div>
    </main>
  );
}
