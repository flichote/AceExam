import type { LeaderboardResponse, LeaderboardItem } from "@/types";

/**
 * 排行榜 mock（docs/api.md §11.6）
 * TODO(ep-backend): GET /leaderboard 就绪后移除
 * 口径：主排序 total_correct 降序，次排序 accuracy（样本 ≥ 30 题）；<30 题不进榜。
 */

const NAMES = [
  "张伟", "李娜", "王强", "刘洋", "陈静", "杨帆", "赵磊", "黄敏",
  "周杰", "吴倩", "徐亮", "孙悦", "马超", "朱婷", "胡歌", "郭靖",
  "林黛玉", "孙悟空", "诸葛亮", "李白", "杜甫", "王阳明", "苏轼", "辛弃疾",
  "李清照", "陆游", "白居易", "韩愈", "柳宗元", "王安石", "欧阳修", "曾巩",
];

function seededAccuracy(i: number): number {
  // 名次靠前正确率更高（0.55 ~ 0.98）
  return Math.min(0.98, 0.55 + (30 - i) * 0.015 + ((i * 7) % 5) * 0.01);
}

export function mockLeaderboard(opts: {
  scope?: "global" | "subject";
  subjectId?: string;
  page?: number;
  pageSize?: number;
} = {}): LeaderboardResponse {
  const scope = opts.scope ?? "global";
  const page = opts.page ?? 1;
  const pageSize = opts.pageSize ?? 20;

  const items: LeaderboardItem[] = NAMES.map((username, i) => {
    const questions_practiced = 60 + (NAMES.length - i) * 23;
    const accuracy = seededAccuracy(i);
    return {
      rank: i + 1,
      user_id: `user-${i + 1}`,
      username,
      total_correct: Math.round(questions_practiced * accuracy),
      questions_practiced,
      accuracy,
      current_streak: (i * 3) % 15,
    };
  });

  // 分页模拟
  const start = (page - 1) * pageSize;
  const paged = items.slice(start, start + pageSize);

  return {
    scope,
    items: paged,
    page,
    page_size: pageSize,
    total: items.length,
    me: {
      rank: 42,
      total_correct: 180,
      questions_practiced: 260,
      accuracy: 0.692,
    },
  };
}
