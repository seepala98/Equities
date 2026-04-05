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

export const portfolio = {
  list: () => api.get('/portfolios/'),
  create: (data) => api.post('/portfolios/create/', data),
  detail: (id) => api.get(`/portfolios/${id}/`),
  delete: (id) => api.delete(`/portfolios/${id}/`),
  
  parse: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/portfolios/parse/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  
  parseMultiple: (files) => {
    const formData = new FormData()
    files.forEach((file, index) => {
      formData.append(`file_${index}`, file)
    })
    return api.post('/portfolios/parse-multiple/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  
  import: (data) => api.post('/portfolios/import/', data),
  
  transactions: (id, params) => api.get(`/portfolios/${id}/transactions/`, { params }),
  holdings: (id) => api.get(`/portfolios/${id}/holdings/`),
  performance: (id, params) => api.get(`/portfolios/${id}/performance/`, { params }),
  heatmap: (id) => api.get(`/portfolios/${id}/heatmap/`),
  dateRange: (id) => api.get(`/portfolios/${id}/date-range/`),
}
