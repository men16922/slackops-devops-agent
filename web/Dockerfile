# 대시보드 + 시드 공용 이미지 (node:20-alpine).
# web 서비스는 `next start`, seed 서비스는 `node scripts/seed.mjs` 로 같은 이미지를 재사용.
FROM node:20-alpine

WORKDIR /app

# 의존성 먼저(레이어 캐시).
COPY package.json ./
RUN npm install

# 소스 + 시드 스크립트.
COPY . .

# 빌드(.next 생성). seed 서비스도 이 이미지를 쓰지만 빌드 산출물은 무시하고 스크립트만 실행.
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
