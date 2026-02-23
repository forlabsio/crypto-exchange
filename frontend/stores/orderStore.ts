import { create } from "zustand";
import { apiFetch } from "@/lib/api";

interface Order {
  id: number;
  pair: string;
  side: string;
  type: string;
  price: string;
  quantity: string;
  status: string;
}

interface OrderStore {
  openOrders: Order[];
  orderHistory: Order[];
  fetchOpenOrders: () => Promise<void>;
  fetchHistory: () => Promise<void>;
  placeOrder: (order: {
    pair: string;
    side: string;
    type: string;
    quantity: number;
    price?: number;
  }) => Promise<void>;
  cancelOrder: (id: number) => Promise<void>;
}

export const useOrderStore = create<OrderStore>((set) => ({
  openOrders: [],
  orderHistory: [],
  fetchOpenOrders: async () => {
    const data = await apiFetch("/api/orders/open");
    set({ openOrders: data });
  },
  fetchHistory: async () => {
    const data = await apiFetch("/api/orders/history");
    set({ orderHistory: data });
  },
  placeOrder: async (order) => {
    await apiFetch("/api/orders", { method: "POST", body: JSON.stringify(order) });
  },
  cancelOrder: async (id) => {
    await apiFetch(`/api/orders/${id}`, { method: "DELETE" });
  },
}));
