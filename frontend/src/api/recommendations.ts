import { apiClient } from './client.ts'
import type { RecommendationRequest, RecommendationResponse } from './types.ts'

export async function getSafeRecommendations(req: RecommendationRequest): Promise<RecommendationResponse> {
  const { data } = await apiClient.post<RecommendationResponse>('/v1/recommendations', req)
  return data
}
