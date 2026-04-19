import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  return (
    <main className="container mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">RAG Pipeline Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Ingestion Jobs</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">No jobs yet. Submit a URL to get started.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Documents</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">Documents will appear after crawling.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Vector Collections</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">Collections will appear after ingestion.</p>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
