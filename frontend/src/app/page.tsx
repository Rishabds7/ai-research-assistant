"use client";

import { useState, useEffect } from "react";
import { getPapers, uploadPaper, Paper, deleteAllPapers } from "@/lib/api";
import { PaperItem } from "@/components/PaperItem";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input"; // We'll use standard input for file upload
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, UploadCloud, Trash2 } from "lucide-react";
import { ReviewTab } from "@/components/ReviewTab";

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


  const handleButtonClick = () => {
    const input = document.getElementById('file-upload-input') as HTMLInputElement;
    if (input) input.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFiles = Array.from(e.target.files);

      // Filter out files that are already in the list
      const newFiles = selectedFiles.filter(file =>
        !papers.some(p => p.filename === file.name)
      );

      if (newFiles.length < selectedFiles.length) {
        console.warn(`${selectedFiles.length - newFiles.length} files skipped (duplicates).`);
      }

      if (newFiles.length === 0) {
        e.target.value = '';
        return;
      }

      setUploadingCount(prev => prev + newFiles.length);

      // Upload in parallel
      await Promise.all(newFiles.map(async (file) => {
        try {
          const res = await uploadPaper(file);
          const newPaper = { ...res.paper, uploadTaskId: res.task_id };
          setPapers((prev) => [newPaper, ...prev]);
        } catch (e: any) {
          console.error(`Upload failed: ${file.name}`, e);
          alert(`Upload failed for ${file.name}`);
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
    <main className="min-h-screen bg-slate-50 p-8">
      <div className="max-w-5xl mx-auto space-y-8">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">AI Research Assistant</h1>
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
              disabled={uploadingCount > 10} // Just a safety latch
            >
              {uploadingCount > 0 ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Uploading {uploadingCount}...
                </>
              ) : (
                <>
                  <UploadCloud className="mr-2 h-4 w-4" />
                  Upload PDFs
                </>
              )}
            </Button>
          </div>
        </div>

        <Tabs defaultValue="papers" className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-8">
            <TabsTrigger value="papers">📄 Papers</TabsTrigger>
            <TabsTrigger value="review">📋 Review</TabsTrigger>
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

          <TabsContent value="review">
            <ReviewTab papers={papers} onUpdate={fetchPapers} />
          </TabsContent>
        </Tabs>
      </div>
    </main>
  );
}
