import { DatabaseConnection } from "./database";

export interface User {
    id: string;
    username: string;
    email: string;
    roles: string[];
}

export type UserStatus = "active" | "suspended" | "pending";

export class UserRepository {
    private db: DatabaseConnection;

    constructor(db: DatabaseConnection) {
        this.db = db;
    }

    public async findById(id: string): Promise<User | null> {
        return this.db.query("SELECT * FROM users WHERE id = ?", [id]);
    }

    public async findByEmail(email: string): Promise<User | null> {
        return this.db.query("SELECT * FROM users WHERE email = ?", [email]);
    }
}

export const createDefaultUser = (): User => {
    return {
        id: "default-001",
        username: "guest",
        email: "guest@example.com",
        roles: ["guest"],
    };
};
