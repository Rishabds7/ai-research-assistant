"use client";

import { useState, useEffect } from "react";
import { getPapers, uploadPaper, Paper, deleteAllPapers } from "@/lib/api";
import { PaperItem } from "@/components/PaperItem";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input"; // We'll use standard input for file upload
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, UploadCloud, Trash2 } from "lucide-react";
import { useTaskPoll } from "@/hooks/useTaskPoll";

export default function Home() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [uploadingCount, setUploadingCount] = useState(0);


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



  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);
      setUploadingCount(prev => prev + files.length);

      // Process each file
      for (const file of files) {
        // Simple frontend check: is this filename already in our list?
        if (papers.some(p => p.filename === file.name)) {
          alert(`Skip: "${file.name}" is already in your list.`);
          setUploadingCount(prev => Math.max(0, prev - 1));
          continue;
        }

        try {
          const res = await uploadPaper(file);
          // Attaching the task_id to the paper object so PaperItem can poll for it
          const newPaper = { ...res.paper, uploadTaskId: res.task_id };
          setPapers((prev) => [newPaper, ...prev]);
        } catch (e: any) {
          console.error(e);
          const msg = e.response?.data?.error || `Upload failed for ${file.name}`;
          alert(msg);
        } finally {
          setUploadingCount(prev => Math.max(0, prev - 1));
        }
      }
    }
  };

  const handleDeleteAll = async () => {
    if (confirm("Are you sure you want to delete ALL papers? This action cannot be undone.")) {
      try {
        await deleteAllPapers();
        fetchPapers();
      } catch (e) {
        console.error("Failed to delete all papers", e);
        alert("Failed to delete all papers");
      }
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 p-8">
      <div className="max-w-5xl mx-auto space-y-8">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Research Assistant</h1>
            <p className="text-slate-500">Next.js + Django + Celery Implementation</p>
          </div>

          <div className="flex items-center gap-4">
            {papers.length > 0 && (
              <Button
                variant="destructive"
                onClick={handleDeleteAll}
                className="bg-red-50 hover:bg-red-100 text-red-600 border-red-100"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete All
              </Button>
            )}

            {/* Upload Button Wrapper */}
            <div className="relative">
              <input
                type="file"
                accept=".pdf"
                multiple
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={handleFileChange}
                disabled={uploadingCount > 0}
              />
              <Button disabled={uploadingCount > 0}>
                {uploadingCount > 0 ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <UploadCloud className="mr-2 h-4 w-4" />
                )}
                {uploadingCount > 0 ? `Uploading (${uploadingCount})...` : "Upload PDFs"}
              </Button>
            </div>
          </div>
        </div>

        <Tabs defaultValue="papers" className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-8">
            <TabsTrigger value="papers">📄 Papers</TabsTrigger>
            <TabsTrigger value="gaps">🔍 Research Gaps</TabsTrigger>
            <TabsTrigger value="comparison">📊 Comparison</TabsTrigger>
          </TabsList>

          <TabsContent value="papers" className="space-y-4">
            {papers.length === 0 ? (
              <div className="text-center py-20 bg-white rounded-lg border border-dashed border-slate-300">
                <p className="text-slate-500">No papers uploaded yet.</p>
              </div>
            ) : (
              papers.map((paper) => (
                <PaperItem key={paper.id} paper={paper} onUpdate={fetchPapers} />
              ))
            )}
          </TabsContent>

          <TabsContent value="gaps">
            <div className="p-8 bg-white rounded-lg border text-center">
              <p className="text-slate-500">Select papers to analyze gaps (Implementation pending connection to API)</p>
            </div>
          </TabsContent>

          <TabsContent value="comparison">
            <div className="p-8 bg-white rounded-lg border text-center">
              <p className="text-slate-500">Select papers to compare (Implementation pending connection to API)</p>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </main>
  );
}
