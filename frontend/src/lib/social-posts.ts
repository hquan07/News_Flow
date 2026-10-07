import type { SocialPostPerformance } from "@/lib/social-types";

export function deduplicateSocialPosts(
  posts: SocialPostPerformance[],
): SocialPostPerformance[] {
  const seen = new Set<string>();

  return posts.filter((post) => {
    const identity = `${post.source}\u0000${post.post_id}`;
    if (seen.has(identity)) return false;
    seen.add(identity);
    return true;
  });
}
