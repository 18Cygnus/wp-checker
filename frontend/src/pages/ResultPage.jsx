import CoverageDetail from "@/components/result/CoverageDetail";
import DocumentStructure from "@/components/result/DocumentStructure";
import ExecutiveSummary from "@/components/result/ExecutiveSummary";
import RedFlags from "@/components/result/RedFlags";
import ResultHero from "@/components/result/ResultHero";
import SignalBreakdown from "@/components/result/SignalBreakdown";
import { formatScore, getSectionName } from "@/utils/formatters";

function getDominantLabel(distribution) {
  const topEntry = Object.entries(distribution ?? {}).sort((left, right) => (right[1] ?? 0) - (left[1] ?? 0))[0];
  return topEntry ? getSectionName(topEntry[0]) : "Belum diketahui";
}

function buildSignals(data) {
  const signalBreakdown = data?.signal_breakdown ?? {};
  const sections = data?.sections ?? [];
  const keywords = data?.keywords ?? [];
  const keywordsStopwordScored = data?.keywords_stopword_scored ?? [];
  const coverageDetail = data?.coverage_detail ?? {};
  const distribution = data?.label_distribution ?? {};
  const totalSections = sections.length;

  const similarityPercentage = `${Math.round((1 - (Number(signalBreakdown.plagiarism) || 0)) * 100)}%`;
  const missingSections = Object.values(coverageDetail?.tiers ?? {})
    .flatMap((tier) => (tier?.sections ?? []).filter((section) => !section?.detected).map((section) => getSectionName(section?.label)))
    .filter(Boolean);

  return [
    {
      name: "content_balance",
      label: "Keseimbangan Konten",
      score: formatScore(signalBreakdown.content_balance),
      weight: 0.5,
      tier: "primary",
      details: {
        activeSections: `${Object.keys(distribution).length} kategori`,
        dominantLabel: getDominantLabel(distribution),
        averageShare: totalSections ? `${Math.round(100 / Math.max(1, Object.keys(distribution).length))}% rata-rata` : "Belum tersedia",
      },
    },
    {
      name: "profile_aware_coverage",
      label: "Cakupan Berbasis Profil",
      score: formatScore(signalBreakdown.profile_aware_coverage ?? coverageDetail?.percentage),
      weight: 0.2,
      tier: "primary",
      details: {
        coveragePercentage: `${Math.round(Number(coverageDetail?.percentage) || 0)}%`,
        missingSections: missingSections.length ? missingSections.join(", ") : "Tidak ada bagian penting yang hilang",
        profileType: coverageDetail?.profile_type ?? coverageDetail?.profile_used ?? data?.profile_label ?? "undetermined",
      },
    },
    {
      name: "plagiarism",
      label: "Kemiripan dengan Sumber Publik",
      score: formatScore(signalBreakdown.plagiarism),
      weight: 0.25,
      tier: "monitoring",
      details: {
        similarityPercentage,
        flaggedSections: `${(data?.red_flags ?? []).length} temuan`,
      },
    },
    {
      name: "linguistic_quality",
      label: "Kualitas Linguistik",
      score: formatScore(signalBreakdown.linguistic),
      weight: 0.05,
      tier: "supporting",
      details: {
        readabilityScore: `${formatScore(signalBreakdown.linguistic)}/100`,
        issuesCount: `${sections.filter((section) => (section?.confidence ?? 0) < 0.65).length} bagian berconfidence rendah`,
      },
    },
    {
      name: "keyword_extraction",
      label: "Ekstraksi Kata Kunci",
      score: formatScore(signalBreakdown.keyword),
      weight: 0,
      tier: "interpretive",
      details: {
        topKeywordsCount: `${keywordsStopwordScored.length} istilah`,
        categoriesFound: `${new Set(keywords.map((keyword) => keyword?.category).filter(Boolean)).size} kategori`,
        topKeywords: keywordsStopwordScored.slice(0, 40),
      },
    },
  ];
}

export default function ResultPage({ data, onReset }) {
  const signals = buildSignals(data);

  return (
    <>
      <ResultHero data={data} onReset={onReset} />
      <ExecutiveSummary
        headline={data?.summary_headline}
        paragraph={data?.summary_paragraph}
        profileType={data?.coverage_detail?.profile_type ?? data?.coverage_detail?.profile_used ?? data?.profile_label}
        score={data?.credibility_score}
        labelDistribution={data?.label_distribution}
        analysisTime={data?.analysis_time_seconds}
      />
      <RedFlags flags={data?.red_flags} />
      <SignalBreakdown signals={signals} />
      <CoverageDetail
        coverageDetail={data?.coverage_detail}
        labelDistribution={data?.label_distribution}
        sectionCount={data?.sections?.length ?? 0}
      />
      <DocumentStructure sections={data?.sections} />
    </>
  );
}
