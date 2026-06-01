import DisclaimerBand from "@/components/layout/DisclaimerBand";
import Footer from "@/components/layout/Footer";
import NavBar from "@/components/layout/NavBar";
import { useAnalysis } from "@/hooks/useAnalysis";
import IdlePage from "@/pages/IdlePage";
import ResultPage from "@/pages/ResultPage";

export default function App() {
  const { appState, result, error, progress, startAnalysis, reset } = useAnalysis();

  return (
    <div id="beranda" className="min-h-screen bg-surface-primary text-ink-primary">
      <NavBar onReset={appState === "result" ? reset : undefined} />

      <main>
        {appState === "result" && result ? (
          <ResultPage data={result} onReset={reset} />
        ) : (
          <IdlePage
            onUpload={startAnalysis}
            uploadState={appState}
            progress={progress}
            error={error}
          />
        )}
      </main>

      <DisclaimerBand />
      <Footer />
    </div>
  );
}
