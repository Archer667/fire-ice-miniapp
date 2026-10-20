export function countWords(text){return (text.match(/[^\s\ufeff]+/gu)||[]).length}
export function trimWords(text,maximum){let count=0;for(const match of text.matchAll(/[^\s\ufeff]+/gu)){if(++count>maximum)return text.slice(0,match.index)}return text}
