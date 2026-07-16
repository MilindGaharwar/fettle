// .match outside agents//pipeline//llm/ is ordinary string handling
export function slug(name: string) {
  return name.match(/[a-z0-9-]+/g);
}
