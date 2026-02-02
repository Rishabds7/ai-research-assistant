"use client";

import { useState, useEffect } from "react";
import { getPapers, uploadPaper, Paper } from "@/lib/api";
import { PaperItem } from "@/components/PaperItem";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input"; // We'll use standard input for file upload
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, UploadCloud } from "lucide-react";
import { useTaskPoll } from "@/hooks/useTaskPoll";

export default function Home() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadTaskId, setUploadTaskId] = useState<string | null>(null);

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

  // Poll upload task
  const { status: uploadStatus } = useTaskPoll(uploadTaskId, () => {
    setUploadTaskId(null);
    setUploading(false);
    fetchPapers(); // Refresh to show processed status
  });

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setUploading(true);
      try {
        const res = await uploadPaper(file);
        // Res returns { paper, task_id }
        // Add paper immediately to list
        setPapers((prev) => [res.paper, ...prev]);
        setUploadTaskId(res.task_id);
      } catch (e: any) {
        console.error(e);
        const msg = e.response?.data?.error || "Upload failed";
        alert(msg);
        setUploading(false);
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
            {/* Upload Button Wrapper */}
            <div className="relative">
              <input
                type="file"
                accept=".pdf"
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={handleFileChange}
                disabled={uploading}
              />
              <Button disabled={uploading || !!uploadTaskId}>
                {uploading || uploadTaskId ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <UploadCloud className="mr-2 h-4 w-4" />
                )}
                {uploadTaskId ? "Processing..." : "Upload PDF"}
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
