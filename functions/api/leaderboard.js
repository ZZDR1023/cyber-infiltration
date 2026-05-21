// functions/api/leaderboard.js

// 处理 GET 请求：获取排行榜前 10 名
export async function onRequestGet(context) {
    const { env } = context;
    
    try {
      // 执行 SQL 查询，按照分数降序、时间降序排列，取前 10 条
      // 注意：这里的 env.DB 对应着我们后续绑定的 D1 数据库
      const { results } = await env.DB.prepare(`
        SELECT alias, score, survival_time as time, created_at
        FROM leaderboard
        ORDER BY score DESC, survival_time DESC, created_at ASC
        LIMIT 10
      `).all();
  
      return new Response(JSON.stringify({ entries: results }), {
        headers: { "Content-Type": "application/json; charset=utf-8" }
      });
    } catch (error) {
      return new Response(JSON.stringify({ error: error.message, entries: [] }), { status: 500 });
    }
  }
  
  // 处理 POST 请求：玩家碰撞后提交分数
  export async function onRequestPost(context) {
    const { request, env } = context;
  
    try {
      const payload = await request.json();
      
      // 数据清洗与边界防御
      const alias = String(payload.alias || "匿名骇客").trim().slice(0, 20);
      const score = Math.max(0, Math.min(999999999, parseInt(payload.score) || 0));
      const survival_time = Math.max(0.0, Math.min(9999.0, parseFloat(payload.time) || 0));
      const created_at = Date.now();
  
      // 防止恶意刷榜：如果分数太离谱或者数据为空，可以进行基础拦截
      if (!alias || score === 0) {
        return new Response(JSON.stringify({ error: "Invalid data" }), { status: 400 });
      }
  
      // 写入 D1 云数据库
      await env.DB.prepare(`
        INSERT INTO leaderboard (alias, score, survival_time, created_at)
        VALUES (?, ?, ?, ?)
      `).bind(alias, score, survival_time, created_at).run();
  
      // 写入成功后，顺便把最新的前 10 名顺手带回去，减少前端再次请求的开销
      const { results } = await env.DB.prepare(`
        SELECT alias, score, survival_time as time, created_at
        FROM leaderboard
        ORDER BY score DESC, survival_time DESC, created_at ASC
        LIMIT 10
      `).all();
  
      return new Response(JSON.stringify({ success: true, entries: results }), {
        headers: { "Content-Type": "application/json; charset=utf-8" }
      });
  
    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), { status: 500 });
    }
  }