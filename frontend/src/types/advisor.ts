/**
 * Frontend types for RepoDNA Refactoring Advisor (v0.7.0).
 */

export type AdvisorCategory =
  | 'circular_dependency_reduction'
  | 'high_coupling_module_review'
  | 'layer_boundary_improvement'
  | 'oversized_architectural_hub_review';

export type AdvisorSeverity = 'critical' | 'high' | 'medium' | 'low';

export interface RefactoringRecommendation {
  recommendation_id: string;
  target_module: string;
  category: AdvisorCategory;
  severity: AdvisorSeverity;
  title: string;
  description: string;
  evidence_id?: string | null;
  evidence_snippets: string[];
  revision_source: string;
  affected_modules: string[];
  expected_architectural_benefit: string;
  suggested_action_steps: string[];
  risks_and_limitations: string;
  support_level: string;
  metric_delta_preview: Record<string, string | number | boolean | null>;
}

export interface RefactoringAdvisorReport {
  schema_version: string;
  repo_identity: string;
  total_recommendations: number;
  total_modules_analyzed: number;
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  recommendations: RefactoringRecommendation[];
  summary_text: string;
}
