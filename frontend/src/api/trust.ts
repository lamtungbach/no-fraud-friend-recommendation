import { apiClient } from './client.ts'
import type {
  TrustProfile,
  ReasoningTrace,
  SafeFilterRequest,
  SafeFilterResponse,
  SafeReRankRequest,
  SafeReRankResponse,
} from './types.ts'

export async function getTrustProfile(userId: number): Promise<TrustProfile> {
  const { data } = await apiClient.get<TrustProfile>(`/api/v1/trust/${userId}`)
  return data
}

export async function getBatchTrustProfiles(userIds: number[]): Promise<TrustProfile[]> {
  const { data } = await apiClient.post<TrustProfile[]>('/api/v1/trust/batch', {
    user_ids: userIds,
  })
  return data
}

export async function getReasoningTrace(userId: number): Promise<ReasoningTrace> {
  const { data } = await apiClient.post<ReasoningTrace>('/api/v1/trust/reason', {
    user_id: userId,
  })
  return data
}

export async function filterSafeCandidates(req: SafeFilterRequest): Promise<SafeFilterResponse> {
  const { data } = await apiClient.post<SafeFilterResponse>('/api/v1/recommendations/safe-filter', req)
  return data
}

export async function rerankCandidates(req: SafeReRankRequest): Promise<SafeReRankResponse> {
  const { data } = await apiClient.post<SafeReRankResponse>('/api/v1/recommendations/safe-rerank', req)
  return data
}
