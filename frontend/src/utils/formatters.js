const credibilityTextMap = {
  good: "KREDIBEL · SINYAL POSITIF",
  average: "CUKUP KREDIBEL · TELAAH LEBIH LANJUT",
  poor: "KURANG KREDIBEL · PERLU PERHATIAN",
};

const profileTextMap = {
  technical_only: "Cenderung Teknikal",
  investor_oriented: "Berorientasi Investor",
  hybrid: "Profil Hybrid",
  undetermined: "Profil Belum Teridentifikasi",
};

const confidenceTextMap = {
  high: "tinggi",
  medium: "sedang",
  low: "rendah",
  very_low: "sangat rendah",
};

// Current pipeline labels (ALL_LABELS in credibility_scorer.py, normalized to underscore).
// English names match the pen design for CoverageDetail + DocumentStructure.
const sectionNameMap = {
  technical_architecture: "Technical Architecture",
  use_cases_and_ecosystem: "Use Cases and Ecosystem",
  tokenomics: "Tokenomics",
  project_overview: "Project Overview",
  security_and_audit: "Security and Audit",
  risk_and_legal: "Risk and Legal",
  roadmap: "Roadmap",
  governance: "Governance",
  problem_statement: "Problem Statement",
  // Legacy keys (old label schema — kept for backward compatibility)
  introduction: "Introduction",
  solution_proposal: "Solution Proposal",
  team_and_partnerships: "Team and Partnerships",
  risks_and_compliance: "Risks and Compliance",
};

const credibilityColorMap = {
  good: "bg-signal-positive-soft text-signal-positive",
  average: "bg-signal-warn-soft text-signal-warn",
  poor: "bg-signal-alert-soft text-signal-alert",
};

const scoreColorMap = {
  good: "text-signal-positive",
  average: "text-signal-warn",
  poor: "text-signal-alert",
};

export function formatFileSize(bytes) {
  const size = Number(bytes);

  if (!Number.isFinite(size) || size <= 0) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB", "TB"];
  const unitIndex = Math.min(Math.floor(Math.log(size) / Math.log(1024)), units.length - 1);
  const value = size / 1024 ** unitIndex;

  return `${value >= 10 || unitIndex === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unitIndex]}`;
}

export function formatDuration(seconds) {
  const duration = Number(seconds);

  if (!Number.isFinite(duration) || duration <= 0) {
    return "0 detik";
  }

  if (duration < 60) {
    return `${Math.round(duration)} detik`;
  }

  const minutes = Math.floor(duration / 60);
  const remainingSeconds = Math.round(duration % 60);

  if (remainingSeconds === 0) {
    return `${minutes} menit`;
  }

  return `${minutes} menit ${remainingSeconds} detik`;
}

export function formatDate(value) {
  if (!value) {
    return "Tanggal tidak tersedia";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Tanggal tidak tersedia";
  }

  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function formatScore(score) {
  const normalized = Number(score);

  if (!Number.isFinite(normalized)) {
    return 0;
  }

  if (normalized <= 1) {
    return Math.round(normalized * 100);
  }

  return Math.round(normalized);
}

export function getScoreLabel(score) {
  const normalized = formatScore(score);

  if (normalized >= 88) {
    return "Kredibel · Sinyal Positif";
  }

  if (normalized >= 80) {
    return "Cukup Kredibel · Telaah Lebih Lanjut";
  }

  return "Kurang Kredibel · Perlu Perhatian";
}

export function getScoreColor(score) {
  const normalized = formatScore(score);

  if (normalized >= 88) {
    return scoreColorMap.good;
  }

  if (normalized >= 80) {
    return scoreColorMap.average;
  }

  return scoreColorMap.poor;
}

export function getSignalColor(score) {
  return getScoreColor(score);
}

export function getCredibilityText(label) {
  return credibilityTextMap[label] ?? "LABEL KREDIBILITAS BELUM TERSEDIA";
}

export function getProfileText(label) {
  return profileTextMap[label] ?? "Profil belum diketahui";
}

export function getConfidenceText(confidence) {
  return confidenceTextMap[confidence] ?? "tidak diketahui";
}

export function getSectionName(label) {
  return sectionNameMap[label] ?? "Bagian tidak diketahui";
}

export function getSignalLevel(score) {
  const normalizedScore = Number(score);

  if (!Number.isFinite(normalizedScore) || normalizedScore < 0.6) {
    return "lemah";
  }

  if (normalizedScore < 0.85) {
    return "cukup";
  }

  return "kuat";
}

export function getCredibilityColor(label) {
  return credibilityColorMap[label] ?? "bg-surface-muted text-ink-secondary";
}
