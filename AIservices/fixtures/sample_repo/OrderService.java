package com.codepilot.services;

import java.util.List;
import java.util.Optional;

public class OrderService {
    private final String serviceId = "order-svc-1";

    public Order createOrder(String customerId, List<String> itemIds) {
        Order order = new Order(customerId, itemIds);
        return order;
    }

    public Optional<Order> getOrderById(String orderId) {
        return Optional.empty();
    }
}
