export async function onRequestPost(context) {
    // context.env 包含了你在 CF 后台配置的环境变量
    const { request, env } = context;
  
    const FALLBACK_TAUNT = "网络连接中断。你连直面我的资格都没有。";
  
    try {
      const payload = await request.json();
      const alias = payload.alias || "无名骇客";
      const seconds = Number(payload.seconds) || 0;
  
      const systemPrompt = "你是一个冷酷、傲慢、高维度的赛博主机意识，像 Agent Smith 一样俯视入侵者。你的回答必须是中文，最多50个汉字，语气像网络防火墙反派在嘲讽失败的黑客。不要解释，不要换行。";
      const userPrompt = `有一个代号为 ${alias} 的人类黑客试图潜入你的核心数据库，但他只坚持了 ${seconds.toFixed(1)} 秒就被你的基础防火墙拦截了。请用极其傲慢、冷酷且带有一点幽默的赛博朋克反派语气嘲讽他的技术，字数限制在 50 字以内。`;
  
      // 调用智谱 API
      const response = await fetch("https://open.bigmodel.cn/api/paas/v4/chat/completions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // 注意：这里调用了环境变量中的 API KEY
          "Authorization": `Bearer ${env.ZHIPU_API_KEY}` 
        },
        body: JSON.stringify({
          model: "glm-4-flash-250414",
          messages: [
            { role: "system", content: systemPrompt },
            { role: "user", content: userPrompt }
          ],
          temperature: 0.9,
          max_tokens: 90
        })
      });
  
      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }
  
      const data = await response.json();
      const content = data?.choices?.[0]?.message?.content || "";
      
      // 清理换行并截断 50 字
      const cleanContent = content.replace(/\s+/g, " ").trim().slice(0, 50);
  
      return new Response(JSON.stringify({ text: cleanContent || FALLBACK_TAUNT }), {
        headers: { "Content-Type": "application/json" }
      });
  
    } catch (error) {
      console.error("AI Taunt Error:", error);
      // 容灾兜底
      return new Response(JSON.stringify({ text: FALLBACK_TAUNT }), {
        headers: { "Content-Type": "application/json" }
      });
    }
  }