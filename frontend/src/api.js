import axios from 'axios'

const BASE = '/api/v1'

const api = axios.create({ baseURL: BASE })

export const stocks = {
  list: (params) => api.get('/stocks/', { params }),
  latest: (symbol) => api.get(`/stocks/${symbol}/latest/`),
}

export const listings = {
  list: (params) => api.get('/listings/', { params }),
  assetSummary: () => api.get('/listings/asset-summary/'),
}

export const etfs = {
  list: (params) => api.get('/etfs/', { params }),
  popular: () => api.get('/etfs/popular/'),
  detail: (symbol) => api.get(`/etfs/${symbol}/`),
  holdings: (symbol, params) => api.get(`/etfs/${symbol}/holdings/`, { params }),
  fetch: (symbol) => api.post(`/etfs/${symbol}/fetch/`),
  performance: (params) => api.get('/etfs/performance/', { params }),
}

export const sectors = {
  list: () => api.get('/sectors/'),
}

export const enriched = {
  list: (params) => api.get('/enriched/', { params }),
  detail: (symbol) => api.get(`/enriched/${symbol}/`),
}
