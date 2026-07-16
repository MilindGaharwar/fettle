export function parseModelReply(reply: string) {
  return reply.match(/\{.*\}/s);
}
